# core/data_manager.py
import pandas as pd
import streamlit as st
import os
from datetime import datetime, time
from pandas import json_normalize

# --- CONFIGURACIÓN DE RUTAS ---
PATH_AIRE = "parquet_aire"
PATH_METEO = "parquet_meteo"
PATH_TRAFICO = "parquet_trafico"


import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix

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
    path = os.path.join(BASE_DIR, 'parquet_total', 'dataset_total_predNO2.parquet')
    # 2. Mostramos en la app qué ruta está intentando leer exactamente
    st.info(f"Intentando cargar desde: {path}")
    df = pd.read_parquet(path)

    #df = pd.read_parquet('parquet_total/dataset_total_predNO2.parquet')
    return df.sort_values("timestamp")