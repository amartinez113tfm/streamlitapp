import streamlit as st
import pandas as pd
from datetime import datetime
import pymongo
import requests
import dns.resolver
import streamlit as st

from datetime import datetime,timedelta
import dns.resolver
import numpy as np

# Configuracion de DNS para evitar bloqueos en Atlas
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']

def extraer_bloque_24h_produccion(id_estacion_str):
    """
    Extrae los datos de las ultimas 24h reales utilizando una ventana temporal
    fija para garantizar que las tres fuentes traigan las mismas horas exactas.
    """
    MONGO_URI = st.secrets["MONGO_URI"]
    
    try:
        client = pymongo.MongoClient(
            MONGO_URI,
            connectTimeoutMS=5000,
            serverSelectionTimeoutMS=5000
        )
        client.admin.command('ping')
    except Exception as e:
        st.error(f"Error de conexion con MongoDB: {e}")
        return None

    db_aire = client["madrid_aire"]
    db_trafico = client["trafico_madrid"]
    id_estacion_int = int(id_estacion_str)

    # --- DEFINIR VENTANA TEMPORAL COMÚN ---
    # Calculamos la hora actual en punto y restamos 24 horas
    ahora_en_punto = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    hace_24h = ahora_en_punto - timedelta(hours=24)

    # Creamos un filtro de fechas que aplicaremos a las tres colecciones
    filtro_fecha = {"$gte": hace_24h, "$lte": ahora_en_punto}

    # 1. Extraccion con filtro de rango de tiempo (en lugar de solo usar .limit)
    cursor_contam = db_aire["historico_contaminantes"].find({
        "estacion_id": id_estacion_str,
        "timestamp": filtro_fecha
    }).sort("timestamp", pymongo.DESCENDING)
    df_contam = pd.DataFrame(list(cursor_contam))

    cursor_meteo = db_aire["meteorologia"].find({
        "estacion_id": id_estacion_str,
        "timestamp": filtro_fecha
    }).sort("timestamp", pymongo.DESCENDING)
    df_meteo = pd.DataFrame(list(cursor_meteo))

    cursor_trafico = db_trafico["predicciones_horarias"].find({
        "estacion": id_estacion_int,
        "timestamp": filtro_fecha
    }).sort("timestamp", pymongo.DESCENDING)
    df_trafico = pd.DataFrame(list(cursor_trafico))

    # Imprimimos un debug rapido en Streamlit para ver que coleccion se esta quedando corta
    with st.expander("Ver estado de sincronizacion de datos"):
        st.write(f"Ventana buscada: Desde {hace_24h} hasta {ahora_en_punto}")
        st.write(f"Filas encontradas -> Contaminacion: {len(df_contam)} | Meteorologia: {len(df_meteo)} | Trafico: {len(df_trafico)}")

    if df_contam.empty:
        return None

    # 2. Limpieza y redondeo de seguridad
    df_contam["timestamp"] = pd.to_datetime(df_contam["timestamp"]).dt.floor("h")
    df_contam = df_contam.drop_duplicates(subset=["timestamp"])
    if "_id" in df_contam.columns:
        df_contam.drop(columns=["_id"], inplace=True)

    df_final = df_contam.copy()

    # 3. Cruce con Meteorologia
    if not df_meteo.empty:
        if "_id" in df_meteo.columns:
            df_meteo.drop(columns=["_id"], inplace=True)
        if "variables" in df_meteo.columns:
            df_variables = pd.json_normalize(df_meteo["variables"])
            df_meteo = pd.concat([df_meteo.drop(columns=["variables"]), df_variables], axis=1)
            df_meteo.rename(columns={"viento.velocidad": "viento_velocidad", "viento.direccion": "viento_direccion"}, inplace=True)

        df_meteo["timestamp"] = pd.to_datetime(df_meteo["timestamp"]).dt.floor("h")
        df_meteo = df_meteo.drop_duplicates(subset=["timestamp"])
        df_final = pd.merge(df_final, df_meteo, on="timestamp", how="inner", suffixes=('', '_meteo'))

    # 4. Cruce con Trafico
    if not df_trafico.empty:
        if "_id" in df_trafico.columns:
            df_trafico.drop(columns=["_id"], inplace=True)
            
        df_trafico["timestamp"] = pd.to_datetime(df_trafico["timestamp"]).dt.floor("h")
        df_trafico = df_trafico.drop_duplicates(subset=["timestamp"])
        
        df_trafico_red = df_trafico[["timestamp", "valor"]].rename(columns={"valor": "trafico_valor"})
        df_final = pd.merge(df_final, df_trafico_red, on="timestamp", how="inner")

    # 5. Ordenacion de pasado a presente
    df_final = df_final.sort_values("timestamp").reset_index(drop=True)
    return df_final


def prueba24Horas(id_estacion_str):
    MONGO_URI = st.secrets["MONGO_URI"]
    client = pymongo.MongoClient(MONGO_URI)
    db_aire = client["madrid_aire"]
    db_trafico = client["trafico_madrid"]
    
    with st.spinner("Ejecutando diagnóstico de colecciones..."):
        id_estacion_int = int(id_estacion_str)
        
        # 1. Diagnóstico independiente de CONTAMINACIÓN
        cursor_contam = db_aire["historico_contaminantes"].find(
            {"estacion_id": id_estacion_str}
        ).sort("timestamp", pymongo.DESCENDING).limit(24)
        df_contam = pd.DataFrame(list(cursor_contam))
        
        # 2. Diagnóstico independiente de METEOROLOGÍA
        cursor_meteo = db_aire["meteorologia"].find(
            {"estacion_id": id_estacion_str}
        ).sort("timestamp", pymongo.DESCENDING).limit(24)
        df_meteo = pd.DataFrame(list(cursor_meteo))
        
        # 3. Diagnóstico independiente de TRÁFICO
        cursor_trafico = db_trafico["predicciones_horarias"].find(
            {"estacion": id_estacion_int}
        ).sort("timestamp", pymongo.DESCENDING).limit(24)
        df_trafico = pd.DataFrame(list(cursor_trafico))

    # --- PANEL DE DIAGNÓSTICO EN STREAMLIT ---
    st.subheader("Resultados del Diagnóstico de Datos")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Filas Contaminación", len(df_contam))
        if not df_contam.empty:
            df_contam["timestamp"] = pd.to_datetime(df_contam["timestamp"])
            st.write(f"**Mín:** {df_contam['timestamp'].min()}")
            st.write(f"**Máx:** {df_contam['timestamp'].max()}")
        else:
            st.error("Colección vacía o sin esta estación")

    with col2:
        st.metric("Filas Meteorología", len(df_meteo))
        if not df_meteo.empty:
            df_meteo["timestamp"] = pd.to_datetime(df_meteo["timestamp"])
            st.write(f"**Mín:** {df_meteo['timestamp'].min()}")
            st.write(f"**Máx:** {df_meteo['timestamp'].max()}")
        else:
            st.error("Colección vacía o sin esta estación")

    with col3:
        st.metric("Filas Tráfico", len(df_trafico))
        if not df_trafico.empty:
            df_trafico["timestamp"] = pd.to_datetime(df_trafico["timestamp"])
            st.write(f"**Mín:** {df_trafico['timestamp'].min()}")
            st.write(f"**Máx:** {df_trafico['timestamp'].max()}")
        else:
            st.error("Colección vacía o sin esta estación")

    # --- PROBAR EL CRUCE PASO A PASO ---
    st.subheader("Análisis del Cruce (Merge)")
    
    if df_contam.empty or df_meteo.empty or df_trafico.empty:
        st.error("No se puede realizar el cruce porque una o más fuentes no devolvieron datos.")
    else:
        # Intento de cruce 1: Contaminación + Meteorología
        cruce_1 = pd.merge(df_contam, df_meteo, on="timestamp", how="inner")
        st.write(f"Filas tras juntar Contaminación + Meteorología: **{len(cruce_1)}**")
        
        # Intento de cruce 2: El resultado anterior + Tráfico
        df_trafico_red = df_trafico[["timestamp", "valor"]].rename(columns={"valor": "trafico_valor"})
        cruce_2 = pd.merge(cruce_1, df_trafico_red, on="timestamp", how="inner")
        st.write(f"Filas finales tras añadir Tráfico: **{len(cruce_2)}**")
        
        if len(cruce_2) == 0:
            st.warning("⚠️ El cruce da 0 filas. Esto significa que los timestamps no coinciden exactamente al segundo.")
            st.write("**Ejemplo de fecha en Contaminación:**", str(df_contam["timestamp"].iloc[0]))
            st.write("**Ejemplo de fecha en Meteorología:**", str(df_meteo["timestamp"].iloc[0]))
            st.write("**Ejemplo de fecha en Tráfico:**", str(df_trafico["timestamp"].iloc[0]))


def extraer_bloque_24h_consistente(id_estacion_str):
    """
    Busca la ultima hora comun en las 3 colecciones y extrae las 24h consecutivas 
    hacia atras desde ese punto temporal exacto.
    """
    MONGO_URI = st.secrets["MONGO_URI"]
    try:
        client = pymongo.MongoClient(MONGO_URI, connectTimeoutMS=5000)
        db_aire = client["madrid_aire"]
        db_trafico = client["trafico_madrid"]
    except Exception as e:
        st.error(f"Error de conexion con MongoDB: {e}")
        return None

    id_estacion_int = int(id_estacion_str)

    # 1. Traemos un bloque generoso del historico de las 3 colecciones (ultimos 5 dias)
    # No ponemos tildes en los comentarios de codigo
    cursor_contam = db_aire["historico_contaminantes"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_meteo = db_aire["meteorologia"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_trafico = db_trafico["predicciones_horarias"].find({"estacion": id_estacion_int}).sort("timestamp", -1).limit(120)

    df_contam = pd.DataFrame(list(cursor_contam))
    df_meteo = pd.DataFrame(list(cursor_meteo))
    df_trafico = pd.DataFrame(list(cursor_trafico))

    if df_contam.empty or df_meteo.empty or df_trafico.empty:
        st.error("Una o varias colecciones de MongoDB estan vacias. No se puede calcular el bloque.")
        return None

    # 2. Saneamos y redondeamos los timestamps de cada coleccion a la hora en punto
    for df in [df_contam, df_meteo, df_trafico]:
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("h")
        if "_id" in df.columns:
            df.drop(columns=["_id"], inplace=True)

    # Eliminamos posibles duplicados de hora dentro de cada dataframe para no alterar los cruces
    df_contam = df_contam.drop_duplicates(subset=["timestamp"])
    df_meteo = df_meteo.drop_duplicates(subset=["timestamp"])
    df_trafico = df_trafico.drop_duplicates(subset=["timestamp"])

    # Desanidamos las variables meteorologicas si vienen estructuradas
    if "variables" in df_meteo.columns:
        df_variables = pd.json_normalize(df_meteo["variables"])
        df_meteo = pd.concat([df_meteo.drop(columns=["variables"]), df_variables], axis=1)
        df_meteo.rename(columns={"viento.velocidad": "viento_velocidad", "viento.direccion": "viento_direccion"}, inplace=True)

    # Reducimos trafico a las columnas necesarias para no ensuciar
    df_trafico_red = df_trafico[["timestamp", "valor"]].rename(columns={"valor": "intensidad"})

    # 3. Encontrar la interseccion de horas en las que COINCIDEN las tres colecciones
    horas_contam = set(df_contam["timestamp"])
    horas_meteo = set(df_meteo["timestamp"])
    horas_trafico = set(df_trafico_red["timestamp"])

    horas_comunes = horas_contam.intersection(horas_meteo).intersection(horas_trafico)

    if not horas_comunes:
        st.error("No se ha encontrado ninguna hora comun entre Contaminantes, Meteorologia y Trafico.")
        return None

    # La ultima hora comun disponible sera el valor maximo de nuestro conjunto de interseccion
    ultima_hora_comun = max(horas_comunes)
    
    # 4. Construimos la ventana exacta de 24 horas consecutivas hacia atras
    hora_inicio_ventana = ultima_hora_comun - timedelta(hours=23)
    
    st.info(f"Identificado estado consistente. Generando ventana desde {hora_inicio_ventana} hasta {ultima_hora_comun}")

    # 5. Hacemos el filtrado del bloque de las 24h sobre los datos limpios de contaminantes
    df_contam_24h = df_contam[(df_contam["timestamp"] >= hora_inicio_ventana) & (df_contam["timestamp"] <= ultima_hora_comun)]

    # 6. Realizamos el cruce definitivo (Inner Merge) ya con la certeza de que no se perderan filas
    df_final = pd.merge(df_contam_24h, df_meteo, on="timestamp", how="inner")
    df_final = pd.merge(df_final, df_trafico_red, on="timestamp", how="inner")

    # Ordenamos cronologicamente de pasado a presente (fundamental para la red GRU)
    df_final = df_final.sort_values("timestamp").reset_index(drop=True)

    # Verificacion de seguridad estructural
    if len(df_final) != 24:
        st.warning(f"La ventana seleccionada no tiene las 24 horas consecutivas perfectas (Filas obtenidas: {len(df_final)}). Aplicando ffill.")
        # Si falta alguna hora suelta intermedia en el historico, forzamos un reindex temporal para asegurar las 24 filas
        rango_completo = pd.date_range(start=hora_inicio_ventana, end=ultima_hora_comun, freq="h")
        df_final = df_final.set_index("timestamp").reindex(rango_completo).ffill().bfill()
        df_final = df_final.reset_index().rename(columns={"index": "timestamp"})

    return df_final


def prediccionO3HF(df_final,id_estacion_str):


    # (No ponemos tildes en los comentarios de codigo)
    st.subheader("🔮 Prediccion del horizonte futuro (Proximas 24 horas)")

# 1. Filtramos y preparamos las 7 variables numericas del entrenamiento
    columnas_modelo = ['o3', 'temperatura', 'radiacion_solar', 'humedad', 'intensidad', 'viento_velocidad', 'viento_direccion']
        
        # Transformamos el DataFrame en la lista de diccionarios que Pydantic devora
    registros_json = df_final[columnas_modelo].to_dict(orient="records")
        
        # 2. Construimos el Payload exacto que acabamos de probar con exito en Postman
    payload = {
            "estacion_id": id_estacion_str,
            "historial": registros_json
        }
        
        # URL oficial de tu API recien parcheada
    url_api = "https://amartinez113-tfm.hf.space/predict"
        
    with st.spinner("Conectando con el microservicio en Hugging Face... Ejecutando red GRU..."):
            try:
                response = requests.post(url_api, json=payload, timeout=20)
                
                if response.status_code == 200:
                    resultado = response.json()
                    predicciones_ozono = resultado["predicciones_24h"]
                    
                    st.success("¡Prediccion calculada correctamente por la red neuronal!")
                    
                    # 3. Creamos un DataFrame para graficar el futuro
                    # Generamos las proximas 24 horas a partir de la ultima hora comun del historico
                    ultima_hora = df_final["timestamp"].max()
                    horas_futuras = pd.date_range(start=ultima_hora + pd.Timedelta(hours=1), periods=24, freq="h")
                    
                    df_futuro = pd.DataFrame({
                        "Fecha y Hora": horas_futuras,
                        "Prediccion O₃ (µg/m³)": predicciones_ozono
                    }).set_index("Fecha y Hora")
                    
                    # 4. Pintamos el grafico interactivo final en Streamlit
                    st.line_chart(df_futuro)
                    
                    # Mostramos una tabla expandible con los valores exactos por si quieren consultarlos
                    with st.expander("Ver valores numericos de la prediccion"):
                        st.dataframe(df_futuro.style.format("{:.2f} µg/m³"))
                        
                else:
                    st.error(f"La API devolvio un error: {response.text}")
                    
            except Exception as e:
                st.error(f"No se pudo conectar con el servidor de prediccion: {e}")    
        

def prediccionReal48h(df_final,id_estacion_str):
    columnas_modelo = ['o3', 'humedad', 'precipitacion', 'presion', 'radiacion_solar', 'temperatura',
    'viento_direccion', 'viento_velocidad', 'intensidad', 'laborable', 'hora_sin',
    'hora_cos', 'MES_SIN', 'MES_COS']
    url_api = "https://amartinez113-tfm.hf.space/predict"
    
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
                    
                    st.success("¡Inferencia doble completada con exito por el microservicio!")
                    
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
                    valores_reales = np.append(df_ordenado["o3"].tail(24).values, [np.nan] * 24)
                    
                    # 2. Prediccion de Validacion: Tiene datos en las primeras 24h, y NaN en el futuro
                    valores_validacion = np.append(pred_pasada, [np.nan] * 24)
                    
                    # 3. Prediccion Futura: Tiene NaN en el pasado, y las predicciones en las ultimas 24h
                    valores_futuro = np.append([np.nan] * 24, pred_futura)
                    
                    # --- CREACION DEL DATAFRAME UNIFICADO ---
                    df_grafico = pd.DataFrame({
                        "Fecha y Hora": eje_tiempo_total,
                        "Valor Real O₃": valores_reales,
                        "Prediccion (Validacion Pasado)": valores_validacion,
                        "Prevision Futura": valores_futuro
                    }).set_index("Fecha y Hora")
                    
                    # --- VISUALIZACION ---
                    # Pintamos las 3 curvas superpuestas de forma nativa e interactiva
                    st.line_chart(df_grafico)
                    
                    # Añadimos unas metricas rapidas de error (MAE) para fardar ante el tribunal
                    o3_real_24h = df_ordenado["o3"].tail(24).values
                    mae_validacion = np.mean(np.abs(o3_real_24h - np.array(pred_pasada)))
                    '''
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="Error Medio Absoluto (MAE) de Validacion", value=f"{mae_validacion:.2f} µg/m³")
                    with col2:
                        st.info("💡 Si la curva de Validacion sigue de cerca a la Real, tu red GRU esta generalizando los patrones de trafico y clima como un reloj.")
                    '''
                    # 2. Nueva Metrica: Valor medio previsto para las proximas 24 horas (Futuro)
                    media_prediccion_futura = np.mean(pred_futura)
                    
                    # --- DISEÑO DE FILA DE METRICAS EN STREAMLIT ---
                    # Creamos 3 columnas para que visualmente quede limpio y equilibrado
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            label="Error Medio Absoluto (MAE)", 
                            value=f"{mae_validacion:.2f} µg/m³",
                            help="Mide la desviacion media del modelo sobre los datos reales de las ultimas 24 horas."
                        )
                        
                    with col2:
                        # Determinamos un color o un pequeño texto de estado según la media (opcional para nota)
                        if media_prediccion_futura > 120:
                            estado_aire = "⚠️ Elevado"
                        elif media_prediccion_futura > 50:
                            estado_aire = "✅ Moderado"
                        else:
                            estado_aire = "🟢 Excelente"
                            
                        st.metric(
                            label="Media Prevista (Próximas 24h)", 
                            value=f"{media_prediccion_futura:.2f} µg/m³",
                            delta=estado_aire,
                            delta_color="normal" if media_prediccion_futura <= 120 else "inverse"
                        )
                        
                    with col3:
                        st.info("💡 **Umbrales de Referencia:** El umbral de informacion a la poblacion en Madrid se activa al superar los 180 µg/m³ en una hora.")    
                else:
                    st.error("Hubo un problema con alguna de las llamadas a la API.")
                    
            except Exception as e:
                st.error(f"Error en la conexion o el formateo de series: {e}")


def bloque48h(id_estacion_str):
    """
    Busca la ultima hora comun en las 3 colecciones y extrae las 48h consecutivas 
    hacia atras desde ese punto temporal exacto.
    """
    MONGO_URI = st.secrets["MONGO_URI"]
    try:
        client = pymongo.MongoClient(MONGO_URI, connectTimeoutMS=5000)
        db_aire = client["madrid_aire"]
        db_trafico = client["trafico_madrid"]
    except Exception as e:
        st.error(f"Error de conexion con MongoDB: {e}")
        return None

    id_estacion_int = int(id_estacion_str)

    # 1. Traemos un bloque generoso del historico de las 3 colecciones (ultimos 5 dias)
    # No ponemos tildes en los comentarios de codigo
    cursor_contam = db_aire["historico_contaminantes"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_meteo = db_aire["meteorologia"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_trafico = db_trafico["predicciones_horarias"].find({"estacion": id_estacion_int}).sort("timestamp", -1).limit(120)

    df_contam = pd.DataFrame(list(cursor_contam))
    df_meteo = pd.DataFrame(list(cursor_meteo))
    df_trafico = pd.DataFrame(list(cursor_trafico))

    if df_contam.empty or df_meteo.empty or df_trafico.empty:
        st.error("Una o varias colecciones de MongoDB estan vacias. No se puede calcular el bloque.")
        return None

    # 2. Saneamos y redondeamos los timestamps de cada coleccion a la hora en punto
    for df in [df_contam, df_meteo, df_trafico]:
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("h")
        if "_id" in df.columns:
            df.drop(columns=["_id"], inplace=True)

    # Eliminamos posibles duplicados de hora dentro de cada dataframe para no alterar los cruces
    df_contam = df_contam.drop_duplicates(subset=["timestamp"])
    df_meteo = df_meteo.drop_duplicates(subset=["timestamp"])
    df_trafico = df_trafico.drop_duplicates(subset=["timestamp"])

    # Desanidamos las variables meteorologicas si vienen estructuradas
    if "variables" in df_meteo.columns:
        df_variables = pd.json_normalize(df_meteo["variables"])
        df_meteo = pd.concat([df_meteo.drop(columns=["variables"]), df_variables], axis=1)
        df_meteo.rename(columns={"viento.velocidad": "viento_velocidad", "viento.direccion": "viento_direccion"}, inplace=True)

    # Reducimos trafico a las columnas necesarias para no ensuciar
    df_trafico_red = df_trafico[["timestamp", "valor"]].rename(columns={"valor": "intensidad"})

    # 3. Encontrar la interseccion de horas en las que COINCIDEN las tres colecciones
    horas_contam = set(df_contam["timestamp"])
    horas_meteo = set(df_meteo["timestamp"])
    horas_trafico = set(df_trafico_red["timestamp"])

    horas_comunes = horas_contam.intersection(horas_meteo).intersection(horas_trafico)

    if not horas_comunes:
        st.error("No se ha encontrado ninguna hora comun entre Contaminantes, Meteorologia y Trafico.")
        return None

    # La ultima hora comun disponible sera el valor maximo de nuestro conjunto de interseccion
    ultima_hora_comun = max(horas_comunes)
    
    # 4. Construimos la ventana exacta de 48 horas consecutivas hacia atras (restamos 47 horas)
    hora_inicio_ventana = ultima_hora_comun - timedelta(hours=47)
    
    st.info(f"Identificado estado consistente. Generando ventana desde {hora_inicio_ventana} hasta {ultima_hora_comun}")

    # 5. Hacemos el filtrado del bloque de las 48h sobre los datos limpios de contaminantes
    df_contam_48h = df_contam[(df_contam["timestamp"] >= hora_inicio_ventana) & (df_contam["timestamp"] <= ultima_hora_comun)]

    # 6. Realizamos el cruce definitivo (Inner Merge) ya con la certeza de que no se perderan filas
    df_final = pd.merge(df_contam_48h, df_meteo, on="timestamp", how="inner")
    df_final = pd.merge(df_final, df_trafico_red, on="timestamp", how="inner")

    # Ordenamos cronologicamente de pasado a presente (fundamental para la red GRU)
    df_final = df_final.sort_values("timestamp").reset_index(drop=True)

    # Verificacion de seguridad estructural adaptada a 48 horas
    if len(df_final) != 48:
        st.warning(f"La ventana seleccionada no tiene las 48 horas consecutivas perfectas (Filas obtenidas: {len(df_final)}). Aplicando ffill.")
        # Si falta alguna hora suelta intermedia en el historico, forzamos un reindex temporal para asegurar las 48 filas
        rango_completo = pd.date_range(start=hora_inicio_ventana, end=ultima_hora_comun, freq="h")
        df_final = df_final.set_index("timestamp").reindex(rango_completo).ffill().bfill()
        df_final = df_final.reset_index().rename(columns={"index": "timestamp"})

    return df_final


def bloque48Debug(id_estacion_str):
    
    """
    Busca la ultima hora comun en las 3 colecciones y extrae las 48h consecutivas 
    hacia atras desde ese punto temporal exacto.
    """
    MONGO_URI = st.secrets["MONGO_URI"]
    try:
        client = pymongo.MongoClient(MONGO_URI, connectTimeoutMS=5000)
        db_aire = client["madrid_aire"]
        db_trafico = client["trafico_madrid"]
    except Exception as e:
        st.error(f"Error de conexion con MongoDB: {e}")
        return None

    id_estacion_int = int(id_estacion_str)

    # 1. Traemos un bloque generoso del historico de las 3 colecciones (ultimos 5 dias)
    # No ponemos tildes en los comentarios de codigo
    cursor_contam = db_aire["historico_contaminantes"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_meteo = db_aire["meteorologia"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_trafico = db_trafico["predicciones_horarias"].find({"estacion": id_estacion_int}).sort("timestamp", -1).limit(120)

    df_contam = pd.DataFrame(list(cursor_contam))
    df_meteo = pd.DataFrame(list(cursor_meteo))
    df_trafico = pd.DataFrame(list(cursor_trafico))

    if df_contam.empty or df_meteo.empty or df_trafico.empty:
        st.error("Una o varias colecciones de MongoDB estan vacias. No se puede calcular el bloque.")
        return None

    return df_trafico


def bloque48hCiclicas(id_estacion_str):
    """
    Busca la ultima hora comun en las 3 colecciones y extrae las 48h consecutivas 
    hacia atras desde ese punto temporal exacto.
    """
    MONGO_URI = st.secrets["MONGO_URI"]
    try:
        client = pymongo.MongoClient(MONGO_URI, connectTimeoutMS=5000)
        db_aire = client["madrid_aire"]
        db_trafico = client["trafico_madrid"]
    except Exception as e:
        st.error(f"Error de conexion con MongoDB: {e}")
        return None

    id_estacion_int = int(id_estacion_str)

    # 1. Traemos un bloque generoso del historico de las 3 colecciones (ultimos 5 dias)
    # No ponemos tildes en los comentarios de codigo
    cursor_contam = db_aire["historico_contaminantes"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_meteo = db_aire["meteorologia"].find({"estacion_id": id_estacion_str}).sort("timestamp", -1).limit(120)
    cursor_trafico = db_trafico["predicciones_horarias"].find({"estacion": id_estacion_int}).sort("timestamp", -1).limit(120)

    df_contam = pd.DataFrame(list(cursor_contam))
    df_meteo = pd.DataFrame(list(cursor_meteo))
    df_trafico = pd.DataFrame(list(cursor_trafico))

    if df_contam.empty or df_meteo.empty or df_trafico.empty:
        st.error("Una o varias colecciones de MongoDB estan vacias. No se puede calcular el bloque.")
        return None

    # 2. Saneamos y redondeamos los timestamps de cada coleccion a la hora en punto
    for df in [df_contam, df_meteo, df_trafico]:
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("h")
        if "_id" in df.columns:
            df.drop(columns=["_id"], inplace=True)

    # Eliminamos posibles duplicados de hora dentro de cada dataframe para no alterar los cruces
    df_contam = df_contam.drop_duplicates(subset=["timestamp"])
    df_meteo = df_meteo.drop_duplicates(subset=["timestamp"])
    df_trafico = df_trafico.drop_duplicates(subset=["timestamp"])

    # Desanidamos las variables meteorologicas si vienen estructuradas
    if "variables" in df_meteo.columns:
        df_variables = pd.json_normalize(df_meteo["variables"])
        df_meteo = pd.concat([df_meteo.drop(columns=["variables"]), df_variables], axis=1)
        df_meteo.rename(columns={"viento.velocidad": "viento_velocidad", "viento.direccion": "viento_direccion"}, inplace=True)

    # Reducimos trafico a las columnas necesarias para no ensuciar
    df_trafico_red = df_trafico[["timestamp", "valor"]].rename(columns={"valor": "intensidad"})

    # 3. Encontrar la interseccion de horas en las que COINCIDEN las tres colecciones
    horas_contam = set(df_contam["timestamp"])
    horas_meteo = set(df_meteo["timestamp"])
    horas_trafico = set(df_trafico_red["timestamp"])

    horas_comunes = horas_contam.intersection(horas_meteo).intersection(horas_trafico)

    if not horas_comunes:
        st.error("No se ha encontrado ninguna hora comun entre Contaminantes, Meteorologia y Trafico.")
        return None

    # La ultima hora comun disponible sera el valor maximo de nuestro conjunto de interseccion
    ultima_hora_comun = max(horas_comunes)
    
    # 4. Construimos la ventana exacta de 48 horas consecutivas hacia atras (restamos 47 horas)
    hora_inicio_ventana = ultima_hora_comun - timedelta(hours=47)
    
    st.info(f"Identificado estado consistente. Generando ventana desde {hora_inicio_ventana} hasta {ultima_hora_comun}")

    # 5. Hacemos el filtrado del bloque de las 48h sobre los datos limpios de contaminantes
    df_contam_48h = df_contam[(df_contam["timestamp"] >= hora_inicio_ventana) & (df_contam["timestamp"] <= ultima_hora_comun)]

    # 6. Realizamos el cruce definitivo (Inner Merge) ya con la certeza de que no se perderan filas
    df_final = pd.merge(df_contam_48h, df_meteo, on="timestamp", how="inner")
    df_final = pd.merge(df_final, df_trafico_red, on="timestamp", how="inner")

    # Ordenamos cronologicamente de pasado a presente (fundamental para la red GRU)
    df_final = df_final.sort_values("timestamp").reset_index(drop=True)

    # Verificacion de seguridad estructural adaptada a 48 horas
    if len(df_final) != 48:
        st.warning(f"La ventana seleccionada no tiene las 48 horas consecutivas perfectas (Filas obtenidas: {len(df_final)}). Aplicando ffill.")
        # Si falta alguna hora suelta intermedia en el historico, forzamos un reindex temporal para asegurar las 48 filas
        rango_completo = pd.date_range(start=hora_inicio_ventana, end=ultima_hora_comun, freq="h")
        df_final = df_final.set_index("timestamp").reindex(rango_completo).ffill().bfill()
        df_final = df_final.reset_index().rename(columns={"index": "timestamp"})

    # ==============================================================================
    # 7. INYECCION DE LAS NUEVAS VARIABLES CICLICAS Y CALENDARIO
    # ==============================================================================
    # Convertimos los dias de la semana a enteros (0=Lunes, 6=Domingo)
    # Los dias laborables seran de Lunes (0) a Viernes (4)
    day_of_week = df_final["timestamp"].dt.dayofweek
    df_final["laborable"] = np.where(day_of_week < 5, 1, 0)

    # Componentes ciclicas para la hora (Periodo de 24 horas)
    horas_raw = df_final["timestamp"].dt.hour
    df_final["hora_sin"] = np.sin(2 * np.pi * horas_raw / 24.0)
    df_final["hora_cos"] = np.cos(2 * np.pi * horas_raw / 24.0)

    # Componentes ciclicas para el mes (Periodo de 12 meses)
    meses_raw = df_final["timestamp"].dt.month
    df_final["MES_SIN"] = np.sin(2 * np.pi * meses_raw / 12.0)
    df_final["MES_COS"] = np.cos(2 * np.pi * meses_raw / 12.0)

    return df_final



import streamlit as st
import pandas as pd
import numpy as np
import requests
import altair as alt
# No ponemos tildes en los comentarios de codigo

def prediccionReal48h_2(df_final, id_estacion_str):
    columnas_modelo = [
        'o3', 'humedad', 'precipitacion', 'presion', 'radiacion_solar', 'temperatura',
        'viento_direccion', 'viento_velocidad', 'intensidad', 'laborable', 'hora_sin',
        'hora_cos', 'MES_SIN', 'MES_COS'
    ]
    url_api = "https://amartinez113-tfm.hf.space/predict"
    
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
                    
                    st.success("¡Inferencia doble completada con exito por el microservicio!")
                    
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
                    valores_reales = np.append(df_ordenado["o3"].tail(24).values, [np.nan] * 24)
                    
                    # 2. Prediccion de Validacion: Tiene datos en las primeras 24h, y NaN en el futuro
                    valores_validacion = np.append(pred_pasada, [np.nan] * 24)
                    
                    # 3. Prediccion Futura: Tiene NaN en el pasado, y las predicciones en las ultimas 24h
                    valores_futuro = np.append([np.nan] * 24, pred_futura)
                    
                    # --- CREACION DEL DATAFRAME UNIFICADO ---
                    df_grafico = pd.DataFrame({
                        "Fecha y Hora": eje_tiempo_total,
                        "Valor Real O₃": valores_reales,
                        "Prediccion (Validacion Pasado)": valores_validacion,
                        "Prevision Futura": valores_futuro
                    }).set_index("Fecha y Hora")
                    
                    # --- CALCULO METRICAS PREVIO AL GRAFICO (Necesario para la banda) ---
                    o3_real_24h = df_ordenado["o3"].tail(24).values
                    mae_validacion = np.mean(np.abs(o3_real_24h - np.array(pred_pasada)))
                    media_prediccion_futura = np.mean(pred_futura)
                    
                    # --- CONSTRUCCION DEL GRAFICO MULTI-CAPA CON ALTAIR ---
                    # --- CONSTRUCCION DEL GRAFICO MULTI-CAPA CON ALTAIR ---
                    # --- CONSTRUCCION DEL GRAFICO MULTI-CAPA CON ALTAIR ---
                    # Pasamos el indice a una columna normal para que Altair la procese bien
                    df_altair = df_grafico.reset_index()
                    
                    # Añadimos las fronteras de la banda de error basandonos en tu MAE real obtenido
                    df_altair["Prevision_Sup"] = df_altair["Prevision Futura"] + mae_validacion
                    df_altair["Prevision_Inf"] = df_altair["Prevision Futura"] - mae_validacion
                    
                    # Capa 1: Area sombreada de la incertidumbre (Banda MAE)
                    banda_error = alt.Chart(df_altair).mark_area(
                        opacity=0.15,
                        color="#2ca02c"  # Mismo tono verde de la prevision futura
                    ).encode(
                        x=alt.X("Fecha y Hora:T", title="Fecha y Hora"),
                        y=alt.Y("Prevision_Sup:Q", title="Ozono (µg/m³)"),
                        y2=alt.Y2("Prevision_Inf:Q")
                    )
                    
                    # Capa 2: Dibujo de las 3 curvas principales
                    df_long = df_altair.melt(
                        id_vars=["Fecha y Hora"], 
                        value_vars=["Valor Real O₃", "Prediccion (Validacion Pasado)", "Prevision Futura"],
                        var_name="Serie", 
                        value_name="Ozono (µg/m³)"
                    )
                    
                    lineas = alt.Chart(df_long).mark_line(strokeWidth=2.5).encode(
                        x=alt.X("Fecha y Hora:T"),
                        y=alt.Y("Ozono (µg/m³):Q"),
                        color=alt.Color("Serie:N", scale=alt.Scale(
                            domain=["Valor Real O₃", "Prediccion (Validacion Pasado)", "Prevision Futura"],
                            range=["#e31a1c", "#1f77b4", "#2ca02c"]  # Rojo, Azul y Verde
                        ))
                    )
                    
                    # Capa 3: Selector interactivo corregido sin atributos externos
                    puntos_interactivos = alt.Chart(df_long).mark_point(
                        size=60, 
                        opacity=0.01  # Casi invisible pero capta el raton perfectamente
                    ).encode(
                        x=alt.X("Fecha y Hora:T"),
                        y=alt.Y("Ozono (µg/m³):Q"),
                        color=alt.Color("Serie:N", legend=None),
                        tooltip=["Fecha y Hora:T", "Serie:N", "Ozono (µg/m³):Q"]
                    )
                    
                    # Unimos todas las capas, añadimos la interaccion nativa y renderizamos
                    grafico_final = (banda_error + lineas + puntos_interactivos).interactive()
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
                        if media_prediccion_futura > 120:
                            estado_aire = "⚠️ Elevado"
                        elif media_prediccion_futura > 50:
                            estado_aire = "✅ Moderado"
                        else:
                            estado_aire = "🟢 Excelente"
                            
                        st.metric(
                            label="Media Prevista (Próximas 24h)", 
                            value=f"{media_prediccion_futura:.2f} µg/m³",
                            delta=estado_aire,
                            delta_color="normal" if media_prediccion_futura <= 120 else "inverse"
                        )
                        
                    with col3:
                        st.info("💡 **Umbrales de Referencia:** El umbral de informacion a la poblacion en Madrid se activa al superar los 180 µg/m³ en una hora.")    
                else:
                    st.error("Hubo un problema con alguna de las llamadas a la API.")
                    
            except Exception as e:
                st.error(f"Error en la conexion o el formateo de series: {e}")


import streamlit as st
import pandas as pd
import numpy as np
import requests
import altair as alt
# No ponemos tildes en los comentarios de codigo

def prediccionReal48h_3(df_final, id_estacion_str):
    columnas_modelo = [
        'o3', 'humedad', 'precipitacion', 'presion', 'radiacion_solar', 'temperatura',
        'viento_direccion', 'viento_velocidad', 'intensidad', 'laborable', 'hora_sin',
        'hora_cos', 'MES_SIN', 'MES_COS'
    ]
    url_api = "https://amartinez113-tfm.hf.space/predict"
    
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
                    
                    st.success("¡Inferencia doble completada con exito por el microservicio!")
                    
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
                    valores_reales = np.append(df_ordenado["o3"].tail(24).values, [np.nan] * 24)
                    
                    # 2. Prediccion de Validacion: Tiene datos en las primeras 24h, y NaN en el futuro
                    valores_validacion = np.append(pred_pasada, [np.nan] * 24)
                    
                    # 3. Prediccion Futura: Tiene NaN en el pasado, y las predicciones en las ultimas 24h
                    valores_futuro = np.append([np.nan] * 24, pred_futura)
                    
                    # --- CREACION DEL DATAFRAME UNIFICADO ---
                    df_grafico = pd.DataFrame({
                        "Fecha y Hora": eje_tiempo_total,
                        "Valor Real O₃": valores_reales,
                        "Prediccion (Validacion Pasado)": valores_validacion,
                        "Prevision Futura": valores_futuro
                    }).set_index("Fecha y Hora")
                    
                    # --- CALCULO DE METRICAS ---
                    o3_real_24h = df_ordenado["o3"].tail(24).values
                    mae_validacion = np.mean(np.abs(o3_real_24h - np.array(pred_pasada)))
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
                        x="Fecha y Hora:T", y="Valor Real O₃:Q"
                    )
                    linea_real = alt.Chart(df_altair).mark_line(color="#e31a1c", strokeWidth=2).encode(
                        x="Fecha y Hora:T", y="Valor Real O₃:Q"
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
                    linea_umbral = alt.Chart(pd.DataFrame({'y': [180]})).mark_rule(
                        color='#e31a1c',
                        strokeWidth=1.5,
                        strokeDash=[6, 4]
                    ).encode(y='y:Q')

                    # Capa para interactividad y tooltips flotantes
                    df_long = df_altair.melt(
                        id_vars=["Fecha y Hora"], 
                        value_vars=["Valor Real O₃", "Prediccion (Validacion Pasado)", "Prevision Futura"],
                        var_name="Serie", value_name="Ozono (µg/m³)"
                    )
                    puntos_interactivos = alt.Chart(df_long).mark_point(size=60, opacity=0.01).encode(
                        x=alt.X("Fecha y Hora:T", title="Fecha y Hora"),
                        y=alt.Y("Ozono (µg/m³):Q", title="Ozono (µg/m³)", scale=alt.Scale(domain=[0, 210])),
                        color=alt.Color("Serie:N", scale=alt.Scale(
                            domain=["Valor Real O₃", "Prediccion (Validacion Pasado)", "Prevision Futura"],
                            range=["#e31a1c", "#1f77b4", "#2ca02c"]
                        ), legend=alt.Legend(title="Leyenda del Grafico")),
                        tooltip=["Fecha y Hora:T", "Serie:N", "Ozono (µg/m³):Q"]
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
                        if media_prediccion_futura > 120:
                            estado_aire = "⚠️ Elevado"
                        elif media_prediccion_futura > 50:
                            estado_aire = "✅ Moderado"
                        else:
                            estado_aire = "🟢 Excelente"
                            
                        st.metric(
                            label="Media Prevista (Próximas 24h)", 
                            value=f"{media_prediccion_futura:.2f} µg/m³",
                            delta=estado_aire,
                            delta_color="normal" if media_prediccion_futura <= 120 else "inverse"
                        )
                        
                    with col3:
                        st.info("💡 **Umbrales de Referencia:** El umbral de informacion a la poblacion en Madrid se activa al superar los 180 µg/m³ en una hora.")    
                else:
                    st.error("Hubo un problema con alguna de las llamadas a la API.")
                    
            except Exception as e:
                st.error(f"Error en la conexion o el formateo de series: {e}")