#Modelo XGBOOSt
import numpy as np
import pandas as pd
import joblib
import streamlit as st
import altair as alt
import xgboost as xgb
import os

def prepare_features_for_predictionNO2_XGBOOST(df, estacion_id, fecha_inicial, fecha_final):
    # Trabajamos sobre una copia para no alterar el original
    df = df.copy().sort_values('timestamp')
    
    # IMPORTANTE: Filtrar primero la estación para que el lag sea coherente
    df = df[df['estacion_id'].astype(str) == str(estacion_id)].copy()

    # 1. Renombrar columnas a lo que espera el modelo
    df = df.rename(columns={
        'viento_velocidad': 'VEL_VIENTO', 'viento_direccion': 'DIR_VIENTO',
        'temperatura': 'TEMP', 'humedad': 'HUMEDAD', 'presion': 'PRESION',
        'radiacion_solar': 'RAD_SOLAR', 'intensidad': 'INTENSIDAD_PONDERADA',
        'laborable': 'IS_LABORABLE', 'sabado': 'IS_SABADO'
    })

    # 2. Ingeniería de variables (Cíclicas y Calefacción)
    df['hour'] = df['timestamp'].dt.hour
    df['month'] = df['timestamp'].dt.month
    df['HORA_SIN'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['HORA_COS'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['MES_SIN'] = np.sin(2 * np.pi * (df['month']-1) / 12)
    df['MES_COS'] = np.cos(2 * np.pi * (df['month']-1) / 12)
    df['PROXY_CALEF'] = df['month'].apply(lambda x: 1 if x in [11, 12, 1, 2, 3] else 0)

    # 3. El Lag (Crucial para el R2)
    df['NO2_lag24'] = df['no2'].shift(24)

    # 4. One-Hot Encoding de Estaciones (Igual que en el entrenamiento)
    estaciones_modelo = [4, 8, 16, 18, 24, 35, 36, 38, 39, 54, 56, 58, 59]
    for est in estaciones_modelo:
        df[f'EST_{est}'] = 1 if str(est) == str(estacion_id) else 0

    # 5. Limpieza y Recorte
    df = df.dropna(subset=['NO2_lag24'])
    mask = (df['timestamp'].dt.date >= fecha_inicial) & (df['timestamp'].dt.date <= fecha_final)
    df_final = df.loc[mask].copy()
    
    # 6. Definir la lista de features en el orden exacto del entrenamiento
    features_list = [
        "VEL_VIENTO", "DIR_VIENTO", "TEMP", "HUMEDAD", "PRESION", "RAD_SOLAR", 
        "INTENSIDAD_PONDERADA", "HORA_SIN", "HORA_COS", "MES_SIN", "MES_COS", 
        "IS_LABORABLE", "IS_SABADO", "PROXY_CALEF", "EST_4", "EST_8", "EST_16", 
        "EST_18", "EST_24", "EST_35", "EST_36", "EST_38", "EST_39", "EST_54", 
        "EST_56", "EST_58", "EST_59", "NO2_lag24"
    ]

    # Devolvemos SOLO el DataFrame filtrado (para evitar errores de desempaquetado)
    return df_final, features_list

def render_prediction_tab(df_historico, fechaInicio, fechaFin):
    st.header("🔮 Predicción de NO2 con XGBoost")

         
    # Crear el DF de resultados garantizando alineación total
    df_res = pd.DataFrame({
                'Fecha': df_historico['timestamp'],
                'Real': df_historico['no2'],
                'Predicción': df_historico['pred_lgbmNO2']
            })

        # Mostrar Métricas
    #render_error_metrics(df_res.rename(columns={'Real': 'no2'}))

        # Gráfica
    st.line_chart(df_res.set_index('Fecha'))
            
    return df_res
    


def load_prediction_modelNO2XGBoost(model_path=r"predictores\NO2modelo_no2_XGBoost.json"):
    """Carga el modelo XGBoost desde un archivo JSON."""
    try:
        # Inicializamos el objeto Booster de XGBoost
        model = xgb.Booster()
        # Cargamos el archivo JSON
        model.load_model(model_path)
        return model
    except Exception as e:
        st.error(f"Error al cargar el archivo JSON del modelo: {e}")
        return None
    

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

def render_error_metrics(df_comparativa):
    """
    Calcula y muestra métricas de error en la interfaz.
    df_comparativa: DataFrame con 'no2' y 'Predicción'.
    """
    y_real = df_comparativa['no2']
    y_pred = df_comparativa['pred_lgbmNO2']

    # Cálculo de métricas
    mae = mean_absolute_error(y_real, y_pred)
    rmse = np.sqrt(mean_squared_error(y_real, y_pred))
    r2 = r2_score(y_real, y_pred)

    # Diseño en Streamlit
    st.subheader("📊 Evaluación Estadística del Modelo")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="MAE (Error Medio)", value=f"{mae:.2f} µg/m³", 
                  help="Promedio de las diferencias absolutas. Indica cuánto se equivoca el modelo de media.")
    
    with col2:
        st.metric(label="RMSE", value=f"{rmse:.2f} µg/m³", 
                  help="Penaliza más los errores grandes. Ideal para detectar picos mal predichos.")
        
    with col3:
        st.metric(label="R² (Precisión)", value=f"{r2:.2f}", 
                  help="Indica qué porcentaje de la variación del NO2 explica tu modelo (0 a 1).")


