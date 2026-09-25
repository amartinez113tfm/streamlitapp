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


import streamlit as st
import pandas as pd
import numpy as np
import requests
import altair as alt
# No ponemos tildes en los comentarios de codigo

def prediccionReal48h_3(df_final, id_estacion_str):
    columnas_modelo = [
        'no2', 'humedad', 'precipitacion', 'presion', 'radiacion_solar', 'temperatura',
        'viento_direccion', 'viento_velocidad', 'intensidad', 'laborable', 'hora_sin',
        'hora_cos', 'MES_SIN', 'MES_COS'
    ]
    url_api = "https://amartinez113-tfm.hf.space/predict/no2"
    
    # Nos aseguramos de tener datos suficientes en el historico (al menos 48 horas)
    if len(df_final) < 48:
        st.error("Se necesitan al menos 48 horas de datos historicos en MongoDB para realizar la validacion.")
    else:
        with st.spinner("Conectando con la red GRU y procesando ventanas temporales..."):
            try:
                # Ordenamos el dataframe por fecha para no cometer errores de desfase
                df_ordenado = df_final.sort_values("timestamp").reset_index(drop=True)
                
                # --- VENTANA 1: Bloque para predecir el FUTURO (Ultimas 24 horas, de la -24 a la 0) ---
                bloque_futuro = df_ordenado.tail(24)
                payload_futuro = {
                    "estacion_id": id_estacion_str,
                    "historial": bloque_futuro[columnas_modelo].to_dict(orient="records")
                }
                
                # --- VENTANA 2: Bloque para predecir el PASADO (De la hora -48 a la -24) ---
                bloque_pasado = df_ordenado.iloc[-48:-24]
                payload_pasado = {
                    "estacion_id": id_estacion_str,
                    "historial": bloque_pasado[columnas_modelo].to_dict(orient="records")
                }
                
                # Lanzamos ambas peticiones a tu API de Hugging Face
                res_futuro = requests.post(url_api, json=payload_futuro, timeout=20)
                res_pasado = requests.post(url_api, json=payload_pasado, timeout=20)
                
                if res_futuro.status_code == 200 and res_pasado.status_code == 200:
                    pred_futura = res_futuro.json()["predicciones_24h"]
                    pred_pasada = res_pasado.json()["predicciones_24h"]
                    
                    st.success("¡Inferencia no2 doble completada con exito por el microservicio!")
                    
                    # --- CONSTRUCCION DEL EJE TEMPORAL CONTINUO (48 HORAS TOTALES) ---
                    ultima_hora_real = df_ordenado["timestamp"].max()
                    
                    # Fechas del pasado analizado (ultimas 24 horas reales)
                    horas_pasadas = df_ordenado["timestamp"].tail(24).values
                    # Fechas del futuro previsto (proximas 24 horas continuas)
                    horas_futuras = pd.date_range(start=pd.to_datetime(ultima_hora_real) + pd.Timedelta(hours=1), periods=24, freq="h")
                    
                    # Unimos los dos bloques de tiempo para crear un indice continuo de 48 puntos
                    eje_tiempo_total = np.concatenate([horas_pasadas, horas_futuras])
                    
                    # --- ALINEACION DE SERIES ---
                    # 1. Valores Reales: Tienen datos en las primeras 24h, y NaN en el futuro
                    valores_reales = np.append(df_ordenado["no2"].tail(24).values, [np.nan] * 24)
                    
                    # 2. Prediccion de Validacion: Tiene datos en las primeras 24h, y NaN en el futuro
                    valores_validacion = np.append(pred_pasada, [np.nan] * 24)
                    
                    # 3. Prediccion Futura: Tiene NaN en el pasado, y las predicciones en las ultimas 24h
                    valores_futuro = np.append([np.nan] * 24, pred_futura)
                    
                    # --- CREACION DEL DATAFRAME UNIFICADO ---
                    df_grafico = pd.DataFrame({
                        "Fecha y Hora": eje_tiempo_total,
                        "Valor Real NO2": valores_reales,
                        "Prediccion (Validacion Pasado)": valores_validacion,
                        "Prevision Futura": valores_futuro
                    }).set_index("Fecha y Hora")
                    
                    # --- CALCULO DE METRICAS ---
                    no2_real_24h = df_ordenado["no2"].tail(24).values
                    mae_validacion = np.mean(np.abs(no2_real_24h - np.array(pred_pasada)))
                    media_prediccion_futura = np.mean(pred_futura)
                    
                    # --- CONSTRUCCION DEL GRAFICO MULTI-CAPA ESTILO DEGRADADO CON ALTAIR ---
                    df_altair = df_grafico.reset_index()
                    
                    # Definicion de los degradados lineales para cada serie (desvanecimiento hacia abajo)
                    gradiente_azul = alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color='rgba(31, 119, 180, 0.4)', offset=0),
                               alt.GradientStop(color='rgba(31, 119, 180, 0.0)', offset=1)]
                    )
                    gradiente_rojo = alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color='rgba(227, 26, 28, 0.4)', offset=0),
                               alt.GradientStop(color='rgba(227, 26, 28, 0.0)', offset=1)]
                    )
                    gradiente_verde = alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color='rgba(44, 160, 44, 0.4)', offset=0),
                               alt.GradientStop(color='rgba(44, 160, 44, 0.0)', offset=1)]
                    )

                    # Capa de Relleno y Linea para Serie Pasado (Azul)
                    area_pasado = alt.Chart(df_altair).mark_area(fill=gradiente_azul).encode(
                        x="Fecha y Hora:T", y="Prediccion (Validacion Pasado):Q"
                    )
                    linea_pasado = alt.Chart(df_altair).mark_line(color="#1f77b4", strokeWidth=2).encode(
                        x="Fecha y Hora:T", y="Prediccion (Validacion Pasado):Q"
                    )

                    # Capa de Relleno y Linea para Serie Real (Rojo)
                    area_real = alt.Chart(df_altair).mark_area(fill=gradiente_rojo).encode(
                        x="Fecha y Hora:T", y="Valor Real NO2:Q"
                    )
                    linea_real = alt.Chart(df_altair).mark_line(color="#e31a1c", strokeWidth=2).encode(
                        x="Fecha y Hora:T", y="Valor Real NO2:Q"
                    )

                    # Capa de Relleno, Linea y Banda MAE para Serie Futuro (Verde)
                    df_altair["Prevision_Sup"] = df_altair["Prevision Futura"] + mae_validacion
                    df_altair["Prevision_Inf"] = df_altair["Prevision Futura"] - mae_validacion
                    
                    banda_error = alt.Chart(df_altair).mark_area(opacity=0.08, color="#2ca02c").encode(
                        x="Fecha y Hora:T", y="Prevision_Sup:Q", y2="Prevision_Inf:Q"
                    )
                    area_futuro = alt.Chart(df_altair).mark_area(fill=gradiente_verde).encode(
                        x="Fecha y Hora:T", y="Prevision Futura:Q"
                    )
                    linea_futuro = alt.Chart(df_altair).mark_line(color="#2ca02c", strokeWidth=2).encode(
                        x="Fecha y Hora:T", y="Prevision Futura:Q"
                    )

                    # Linea de referencia discontinua (Umbral de informacion de Ozono a 180)
                    linea_umbral = alt.Chart(pd.DataFrame({'y': [200]})).mark_rule(
                        color='#e31a1c',
                        strokeWidth=1.5,
                        strokeDash=[6, 4]
                    ).encode(y='y:Q')

                    # Capa para interactividad y tooltips flotantes
                    df_long = df_altair.melt(
                        id_vars=["Fecha y Hora"], 
                        value_vars=["Valor Real NO2", "Prediccion (Validacion Pasado)", "Prevision Futura"],
                        var_name="Serie", value_name="NO2 (µg/m³)"
                    )
                    puntos_interactivos = alt.Chart(df_long).mark_point(size=60, opacity=0.01).encode(
                        x=alt.X("Fecha y Hora:T", title="Fecha y Hora"),
                        y=alt.Y("NO2 (µg/m³):Q", title="NO2 (µg/m³)", scale=alt.Scale(domain=[0, 210])),
                        color=alt.Color("Serie:N", scale=alt.Scale(
                            domain=["Valor Real NO2", "Prediccion (Validacion Pasado)", "Prevision Futura"],
                            range=["#e31a1c", "#1f77b4", "#2ca02c"]
                        ), legend=alt.Legend(title="Leyenda del Grafico")),
                        tooltip=["Fecha y Hora:T", "Serie:N", "NO2 (µg/m³):Q"]
                    )

                    # Ensamblado del lienzo completo por capas
                    grafico_final = (
                        banda_error + area_pasado + linea_pasado + 
                        area_real + linea_real + area_futuro + 
                        linea_futuro + linea_umbral + puntos_interactivos
                    ).properties(height=380).interactive()

                    st.altair_chart(grafico_final, use_container_width=True)
                    
                    # --- DISEÑO DE FILA DE METRICAS EN STREAMLIT ---
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            label="Error Medio Absoluto (MAE)", 
                            value=f"{mae_validacion:.2f} µg/m³",
                            help="Mide la desviacion media del modelo sobre los datos reales de las ultimas 24 horas."
                        )
                        
                    with col2:
                        if media_prediccion_futura > 100:
                            estado_aire = "⚠️ Elevado"
                        elif media_prediccion_futura > 40:
                            estado_aire = "✅ Moderado"
                        else:
                            estado_aire = "🟢 Excelente"
                            
                        st.metric(
                            label="Media Prevista (Próximas 24h)", 
                            value=f"{media_prediccion_futura:.2f} µg/m³",
                            delta=estado_aire,
                            delta_color="normal" if media_prediccion_futura <= 100 else "inverse"
                        )
                        
                    with col3:
                        st.info("💡 **Umbrales de Referencia:** El umbral de informacion a la poblacion en Madrid se activa al superar los 200 µg/m³ en una hora.")    
                else:
                    st.error("Hubo un problema con alguna de las llamadas a la API.")
                    
            except Exception as e:
                st.error(f"Error en la conexion o el formateo de series: {e}")