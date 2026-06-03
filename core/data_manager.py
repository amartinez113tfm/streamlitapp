# core/data_manager.py
import pandas as pd
import streamlit as st
import os
from datetime import datetime, time
from pandas import json_normalize

import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix

# --- CONFIGURACIÓN DE RUTAS ---
PATH_AIRE = "parquet_aire"
PATH_METEO = "parquet_meteo"
PATH_TRAFICO = "parquet_trafico"




# Diccionario con las coordenadas reales de las estaciones de Madrid
DICC_ESTACIONES = {
    4:  {"nombre": "Plaza de España", "lat": 40.423853, "lon": -3.712257},
    8:  {"nombre": "Escuelas Aguirre", "lat": 40.421553, "lon": -3.682319},
    16:  {"nombre": "Arturo Soria", "lat": 40.3947, "lon": -3.7318},
    18: {"nombre": "Farolillo", "lat": 40.419358, "lon": -3.747347},
    24: {"nombre": "Casa de Campo", "lat": 40.419358, "lon": -3.747347},
    35: {"nombre": "Plaza del Carmen", "lat": 40.419208, "lon": -3.703164},
    36: {"nombre": "Moratalaz", "lat": 40.407983, "lon": -3.645314},
    38: {"nombre": "Cuatro Caminos", "lat": 40.445544, "lon": -3.707131},
    39: {"nombre": "Barrio del Pilar", "lat": 40.478233, "lon": -3.711542},
    54: {"nombre": "Ensanche de Vallecas", "lat": 40.372833, "lon": -3.616342},
    56: {"nombre": "Plaza Elíptica", "lat": 40.385039, "lon": -3.718692},
    58: {"nombre": "El Pardo", "lat": 40.521822, "lon": -3.774536},
    59: {"nombre": "Juan Carlos I", "lat": 40.465250, "lon": -3.610514}
}

import pandas as pd
import numpy as np

def calcular_superaciones_anuales(df):
    """
    Calcula el número de veces al año que cada estación supera los límites legales.
    - NO2 y O3: Evaluación horaria (picos de contaminación).
    - PM10 y PM2.5: Evaluación diaria (medias de 24h) según directivas y OMS.
    """
    # 1. Asegurar formato datetime en el timestamp y extraer el año
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    df_analisis = df.copy()
    df_analisis['Anio'] = df_analisis['timestamp'].dt.year
    df_analisis['Fecha_Dia'] = df_analisis['timestamp'].dt.date # Para la agrupación diaria
    
    # 2. Definir los límites normativos y su tipo de métrica
    CONFIG_LIMITES = {
        'no2': {'limite': 200, 'tipo': 'horario', 'unidades': 'µg/m³ (Horario)'},
        'o3':  {'limite': 180, 'tipo': 'horario', 'unidades': 'µg/m³ (Horario)'},
        'pm10': {'limite': 50,  'tipo': 'diario',  'unidades': 'µg/m³ (Media 24h)'},
        'pm2_5': {'limite': 15, 'tipo': 'diario',  'unidades': 'µg/m³ (Media 24h)'} # Criterio OMS
    }
    
    # Identificar todas las columnas de las estaciones (one-hot encoding)
    columnas_estaciones = [c for c in df_analisis.columns if c.startswith('estacion_id_')]
    
    resultados = []
    
    # 3. Iterar por Año, Contaminante y Estación
    for anio, df_anio in df_analisis.groupby('Anio'):
        for contaminante, config in CONFIG_LIMITES.items():
            # Si el contaminante no existe en el DataFrame, saltamos al siguiente
            if contaminante not in df_anio.columns:
                continue
                
            limite = config['limite']
            tipo_calculo = config['tipo']
            
            for col_estacion in columnas_estaciones:
                id_num = int(col_estacion.split('_')[-1])
                # Obtenemos el nombre real usando tu diccionario global DICC_ESTACIONES
                nombre_estacion = DICC_ESTACIONES.get(id_num, {}).get('nombre', f"Estación {id_num}")
                
                # Filtrar los registros donde esta estación específica estuvo activa (valor == 1)
                df_estacion = df_anio[df_anio[col_estacion] == 1]
                
                if not df_estacion.empty:
                    
                    # 🟢 CASO A: EVALUACIÓN DIARIA (Para PM10 y PM2.5)
                    if tipo_calculo == 'diario':
                        # Agrupamos por día para obtener la media de 24 horas reales de esa estación
                        df_diario = df_estacion.groupby('Fecha_Dia')[contaminante].mean().reset_index()
                        # Contamos cuántos días enteros superaron el umbral
                        num_superaciones = (df_diario[contaminante] > limite).sum()
                    
                    # 🟢 CASO B: EVALUACIÓN HORARIA (Para NO2 y O3)
                    else:
                        # Contamos directamente las filas (horas) individuales que superan el límite
                        num_superaciones = (df_estacion[contaminante] > limite).sum()
                    
                    # Guardamos el registro consolidado anual
                    resultados.append({
                        "Año": anio,
                        "Estación": nombre_estacion,
                        "Contaminante": contaminante.upper().replace('_', '.'), # Cambia PM2_5 a PM2.5
                        "Límite Aplicado": f"{limite} {config['unidades']}",
                        "Veces Superado": int(num_superaciones)
                    })
                    
    # Convertimos la lista de resultados en un DataFrame limpio listo para Altair
    df_superaciones = pd.DataFrame(resultados)
    return df_superaciones


def obtener_matriz_confusion(df_filtrado, col_real, limite):
    # Creamos las etiquetas binarias
    y_real = (df_filtrado[col_real] > limite).astype(int)
    y_pred = (df_filtrado['pred_lgbmNO2'] > limite).astype(int)
    
    # Calculamos la matriz
    # Labels [0, 1] asegura que el orden sea: Negativo, Positivo
    cm = confusion_matrix(y_real, y_pred, labels=[0, 1])
    return cm


@st.cache_data
def load_parquet_file(folder, year):
    """Carga, normaliza y renombra columnas base."""
    prefix_map = {
        PATH_AIRE: "aire_madrid_",
        PATH_METEO: "meteo_madrid_",
        PATH_TRAFICO: "trafico_madrid_"
    }
    
    file_name = f"{prefix_map.get(folder)}{year}.parquet"
    file_path = os.path.join(folder, file_name)
    
    try:
        if os.path.exists(file_path):
            df = pd.read_parquet(file_path)
            df.columns = [c.lower() for c in df.columns]
            
            # Normalización de ID de estación
            if 'estacion' in df.columns and 'estacion_id' not in df.columns:
                df = df.rename(columns={'estacion': 'estacion_id'})
            
            # Normalización de Tráfico: valor -> intensidad
            if folder == PATH_TRAFICO and 'valor' in df.columns:
                df = df.rename(columns={'valor': 'intensidad'})

            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
            
            if 'estacion_id' in df.columns:
                df['estacion_id'] = df['estacion_id'].astype(str)
                
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data
def get_combined_data(estacion_id, contaminante, fecha_inicio, fecha_fin):
    años = range(fecha_inicio.year, fecha_fin.year + 1)
    
    df_cont = pd.concat([load_parquet_file(PATH_AIRE, a) for a in años], ignore_index=True)
    df_meteo = pd.concat([load_parquet_file(PATH_METEO, a) for a in años], ignore_index=True)
    df_trafico = pd.concat([load_parquet_file(PATH_TRAFICO, a) for a in años], ignore_index=True)

    # --- BLOQUE DE DIAGNÓSTICO ---
    if not df_trafico.empty:
        print(f"DEBUG TRÁFICO: Se han cargado {len(df_trafico)} filas totales.")
        print(f"DEBUG COLUMNAS: {df_trafico.columns.tolist()}")
        print(f"DEBUG IDS ÚNICOS: {df_trafico['estacion_id'].unique()[:10]}") # Ver los primeros 10 IDs
        print(f"DEBUG VALORES INTENSIDAD: {df_trafico['intensidad'].describe()}")
    else:
        print("DEBUG TRÁFICO: El DataFrame de tráfico está VACÍO tras la carga.")
    if df_cont.empty or df_meteo.empty:
        return pd.DataFrame()

    dt_inicio = datetime.combine(fecha_inicio, time.min)
    dt_fin = datetime.combine(fecha_fin, time.max)
    est_str = str(estacion_id)

    # Filtrado
    df_cont = df_cont[(df_cont['estacion_id'] == est_str) & (df_cont['timestamp'] >= dt_inicio) & (df_cont['timestamp'] <= dt_fin)]
    df_meteo = df_meteo[(df_meteo['estacion_id'] == est_str) & (df_meteo['timestamp'] >= dt_inicio) & (df_meteo['timestamp'] <= dt_fin)]
    
    # Aplanado de Meteorología
    if not df_meteo.empty and 'variables' in df_meteo.columns:
        df_vars = json_normalize(df_meteo['variables'].tolist())
        df_meteo = pd.concat([df_meteo.reset_index(drop=True), df_vars.reset_index(drop=True)], axis=1).drop(columns=['variables'])

    if not df_trafico.empty:
        df_trafico = df_trafico[(df_trafico['estacion_id'] == est_str) & (df_trafico['timestamp'] >= dt_inicio) & (df_trafico['timestamp'] <= dt_fin)]

    # Sincronización
    for d in [df_cont, df_meteo, df_trafico]:
        if not d.empty:
            d['timestamp'] = d['timestamp'].dt.round('min')

    # Merges
    df_final = pd.merge(df_cont, df_meteo, on=["timestamp", "estacion_id"], how="inner")
    
    if not df_trafico.empty:
        df_final = pd.merge(df_final, df_trafico, on=["timestamp", "estacion_id"], how="left")
    
    # Asegurar que intensidad existe aunque el merge falle o no haya datos
    if 'intensidad' not in df_final.columns:
        df_final['intensidad'] = 0.0
    else:
        df_final['intensidad'] = df_final['intensidad'].fillna(0.0)

    df_final.columns = [c.replace('.', '_') for c in df_final.columns]
    return df_final.sort_values("timestamp")

def get_radar_data(df, contaminante):
    """Genera datos para el gráfico de radar evitando KeyErrors."""
    col_cont = contaminante.lower()
    
    # Mapeo de columnas internas a etiquetas legibles
    features = {
        col_cont: contaminante.upper(),
        'intensidad': 'Tráfico',
        'variables_temperatura': 'Temperatura',
        'temperatura': 'Temperatura', # Por si el aplanado no pone el prefijo
        'variables_viento_velocidad': 'Viento',
        'viento_velocidad': 'Viento',
        'variables_humedad': 'Humedad',
        'humedad': 'Humedad'
    }

    if df.empty or col_cont not in df.columns:
        return pd.DataFrame()

    top_5 = df.nlargest(5, col_cont)
    bottom_5 = df.nsmallest(5, col_cont)
    radar_rows = []

    for estado, grupo in [('Máxima Contaminación', top_5), ('Mínima Contaminación', bottom_5)]:
        for col_db, nombre_bonito in features.items():
            # Verificamos si la columna existe en este DF específico antes de operar
            if col_db in df.columns:
                val_medio = grupo[col_db].mean()
                v_min, v_max = df[col_db].min(), df[col_db].max()
                
                denominador = (v_max - v_min)
                norm_val = (val_medio - v_min) / denominador if denominador != 0 else 0
                
                radar_rows.append({
                    'Estado': estado, 
                    'Parámetro': nombre_bonito, 
                    'Valor_Normalizado': float(norm_val)
                })

    return pd.DataFrame(radar_rows)

def get_historical_data(estacion_id, contaminante, fecha_inicio, fecha_fin):
    field_name = contaminante.lower()
    años = range(fecha_inicio.year, fecha_fin.year + 1)
    df_all = pd.concat([load_parquet_file(PATH_AIRE, a) for a in años], ignore_index=True)
    
    if df_all.empty or field_name not in df_all.columns:
        return pd.DataFrame()

    dt_inicio = datetime.combine(fecha_inicio, time.min)
    dt_fin = datetime.combine(fecha_fin, time.max)
    est_str = str(estacion_id)
    
    mask = (df_all['estacion_id'] == est_str) & (df_all['timestamp'] >= dt_inicio) & (df_all['timestamp'] <= dt_fin)
    df = df_all.loc[mask, ['timestamp', field_name]].copy()
    df = df.rename(columns={field_name: f"valor_{contaminante}"})
    return df.sort_values("timestamp")

def get_all_contaminants_monthly(year=None):
    if year:
        df = load_parquet_file(PATH_AIRE, year)
    else:
        files = [f for f in os.listdir(PATH_AIRE) if f.endswith('.parquet')]
        df = pd.concat([pd.read_parquet(os.path.join(PATH_AIRE, f)) for f in files], ignore_index=True)
        df.columns = [c.lower() for c in df.columns]
    
    if df.empty: return df
    df_monthly = df.set_index('timestamp').groupby([pd.Grouper(freq='ME'), 'estacion_id']).mean(numeric_only=True).reset_index()
    return df_monthly

def get_polulant_by_year(year):
    return load_parquet_file(PATH_AIRE, year)

# Stubs de compatibilidad
def get_db_connection(db_name=None): pass
def get_mongodb_client(): pass


#funcion que lee del parquet total con todos los datos y predicciones
def get_datos_parquetTotal(codigo_sel, pollutant_sel, fecha_inicio, fecha_fin):
    df = pd.read_parquet('parquet_total/dataset_total_predNO2.parquet')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    fecha_inicio = pd.to_datetime(fecha_inicio)
    fecha_fin = pd.to_datetime(fecha_fin)
    # 3. Aplicar los filtros
    # Filtramos por el rango de fechas
    mask_fecha = (df['timestamp'] >= fecha_inicio) & (df['timestamp'] <= fecha_fin)

    # Filtramos por la columna dummy de la estacion seleccionada
    columna_estacion = f'estacion_id_{codigo_sel}'

    if columna_estacion in df.columns:
        # Caso normal: la estacion tiene su propia columna
        mask_estacion = (df[columna_estacion] == 1)
    else:
        # Caso especial: es la estacion que se hizo 'drop_first'
        # Es aquella donde TODAS las demas columnas de estaciones son 0
        columnas_otras_estaciones = [c for c in df.columns if 'estacion_id_' in c]
        mask_estacion = (df[columnas_otras_estaciones].sum(axis=1) == 0)

    pollutant_min = pollutant_sel.lower()
    # Creamos el dataframe filtrado
    # Seleccionamos el timestamp, el contaminante elegido y la columna de la estacion
    df_filtrado = df.loc[mask_fecha & mask_estacion].copy()

    # Ordenamos por tiempo para que la serie tenga sentido
    df_filtrado = df_filtrado.sort_values('timestamp')

    #print(f"Datos extraidos para la estacion {codigo_sel} entre {fecha_inicio} y {fecha_fin}")
    #print(df_filtrado.head())

    return df_filtrado.sort_values("timestamp")

# Obtiene la carpeta donde está este script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_todo():
    # Une la carpeta base con tu archivo
    #path = os.path.join(BASE_DIR, 'parquet_total', 'dataset_total_predNO2.parquet')
    # 2. Mostramos en la app qué ruta está intentando leer exactamente
    #st.info(f"Intentando cargar desde: {path}")
    #df = pd.read_parquet(path)

    df = pd.read_parquet('parquet_total/dataset_total_predNO2.parquet')
    return df.sort_values("timestamp")