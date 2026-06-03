import streamlit as st
import folium
from streamlit_folium import st_folium
from datetime import datetime, date
from folium.raster_layers import ImageOverlay
import pandas as pd
import numpy as np
import math

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

def render_copernicus():
    st.set_page_config(layout="wide")
    st.title("Comparativa en Paralelo de Contaminacion")

    fecha_a = st.sidebar.date_input("Selecciona Fecha A", value=None)
    fecha_b = st.sidebar.date_input("Selecciona Fecha B", value=None)

    YOUR_INSTANCE_ID = st.secrets["COPERNICUS_ID"]
    wms_url = "https://shservices.mundi-webservices.com/ogc/wms/YOUR_INSTANCE_ID"
    coordenadas_madrid = [40.416775, -3.703790]

    # Crear dos columnas visuales en la interfaz de Streamlit
    col_izq, col_der = st.columns(2)

    with col_izq:
        if fecha_a:
            st.subheader(f"Estado el {fecha_a}")
            m1 = folium.Map(location=coordenadas_madrid, zoom_start=10)
            folium.WmsTileLayer(
                url=wms_url, layers="NO2", fmt="image/png", transparent=True,
                time=fecha_a.strftime('%Y-%m-%d')
            ).add_to(m1)
            st_folium(m1, width=500, height=450, key="mapa_a")

    with col_der:
        if fecha_b:
            st.subheader(f"Estado el {fecha_b}")
            m2 = folium.Map(location=coordenadas_madrid, zoom_start=10)
            folium.WmsTileLayer(
                url=wms_url, layers="NO2", fmt="image/png", transparent=True,
                time=fecha_b.strftime('%Y-%m-%d')
            ).add_to(m2)
            st_folium(m2, width=500, height=450, key="mapa_b")



def generar_mapa_contaminacion(fecha, capa, instance_id):
    # CHIVATO 1: Ver si la función llega a ejecutarse
    print("\n=== [PAQUETE] Iniciando generar_mapa_contaminacion ===")
    print(f"-> Fecha recibida: {fecha} (Tipo: {type(fecha)})")
    print(f"-> Capa recibida: {capa}")
    print(f"-> Instance ID: {instance_id}")

    coordenadas_madrid = [40.416775, -3.703790]
    m = folium.Map(location=coordenadas_madrid, zoom_start=11, tiles="OpenStreetMap")
    
    # Forzar la conversión de fecha a texto pase lo que pase
    if fecha is not None and fecha != "":
        if not isinstance(fecha, str):
            fecha_str = fecha.strftime("%Y-%m-%d")
        else:
            fecha_str = fecha
            
        print(f"-> Entrando al bloque de renderizado para la fecha: {fecha_str}")
        
        bbox_madrid = "-4.25,39.85,-3.05,41.20"
        
        # 1. Copia AQUÍ tu URL completa del panel (la que empieza por aebfda...)
        url_base_panel = "https://sh.dataspace.copernicus.eu/ogc/wms/aebfda82-f506-448c-9b32-265088990cfd"
        
        # 2. Le concatenamos los parámetros de la petición de la imagen
        url_copernicus = (
            f"{url_base_panel}"
            f"?service=WMS"
            f"&version=1.1.1"
            f"&request=GetMap"
            f"&layers={capa}"  # Asegúrate de que en el panel tu capa se llame igual (ej: NO2)
            f"&format=image/png"
            f"&transparent=true"
            f"&time={fecha_str}"
            f"&srs=EPSG:4326"
            f"&bbox={bbox_madrid}"
            f"&width=600"
            f"&height=400"
        )
        print(f"-> URL GENERADA: {url_copernicus}")
        
        # Añadir la capa al mapa
        try:
            ImageOverlay(
                image=url_copernicus,
                bounds=[[39.85, -4.25], [41.20, -3.05]],
                opacity=0.3,
                name="Copernicus NO2",
                interactive=True,
                cross_origin=False
            ).add_to(m)
            print("-> [ÉXITO] ImageOverlay añadido correctamente al objeto mapa 'm'")
        except Exception as e:
            print(f"-> [ERROR] Falló al añadir el ImageOverlay: {e}")
            
    else:
        print("-> [ALERTA] La fecha llegó vacía (None o ''), saltándose la capa de satélite.")
        
    print("=== [PAQUETE] Fin de la función, retornando mapa ===\n")

    # Creamos una leyenda en HTML flotante para el mapa
    macro_leyenda = """
        <div style="
            position: fixed; 
            bottom: 25px; left: 20px; width: 130px; height: 105px; 
            background-color: rgba(255, 255, 255, 0.9); z-index:9999; font-size:10px;
            border:1px solid #cccccc; border-radius:4px; padding: 6px 8px;
            box-shadow: 1px 1px 4px rgba(0,0,0,0.2); font-family: sans-serif;
        ">
        <b style="font-size: 11px; display: block; margin-bottom: 5px;">Nivel de NO₂</b>
        <div style="margin-bottom: 3px;"><i style="background: #FF0000; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Alta</div>
        <div style="margin-bottom: 3px;"><i style="background: #FFA500; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media-Alta</div>
        <div style="margin-bottom: 3px;"><i style="background: #00FF00; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media</div>
        <div style="margin-bottom: 5px;"><i style="background: #000080; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Baja</div>
        <div style="color: #666666; font-size: 8px; border-top: 1px solid #eeeeee; padding-top: 3px;">
            Valores: 10⁻⁴ mol/m²
        </div>
        </div>
        """
        
        # Añadimos la leyenda al mapa de Folium
    m.get_root().html.add_child(folium.Element(macro_leyenda))
    
    return m



def obtener_datos_tierra_sincronizados(df, fecha_sel, contaminante):
    """
    Filtra tu df_historico para la fecha y el rango horario del satélite,
    y reconstruye la estructura geográfica por estación.
    """
    # 1. Asegurar formato datetime en el timestamp
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
    # 2. Filtrar por el día seleccionado
    df_dia = df[df['timestamp'].dt.date == fecha_sel]
    
    # 3. FILTRADO HORARIO: Nos quedamos con las horas del paso de Sentinel-5P (13h a 15h)
    df_sat_window = df_dia[df_dia['timestamp'].dt.hour.isin([13, 14, 15])]
    
    # Si está vacío el rango específico, usamos el día completo como plan de respaldo
    if df_sat_window.empty:
        df_sat_window = df_dia
        
    registros_estaciones = []
    
    # 4. Desenredar el One-Hot Encoding de las estaciones
    # Buscamos qué columnas de estación_id tienen un '1'
    columnas_estacion = [c for c in df.columns if c.startswith('estacion_id_')]
    
    for col in columnas_estacion:
        id_num = int(col.split('_')[-1])
        
        # Filtramos las filas donde esta estación está activa (valor == 1)
        df_estacion = df_sat_window[df_sat_window[col] == 1]
        
        if not df_estacion.empty:
            # Calculamos la media del contaminante (no2, o3...) en esa franja horaria
            media_valor = df_estacion[contaminante.lower()].mean()
            
            # 🟢 CALCULAMOS LA MEDIA GENERAL DEL VIENTO EN MADRID PARA ESA HORA
            # Usamos .dropna() para evitar que los nulos de algunas estaciones rompan la media
            viento_gen_vel = df_sat_window['viento_velocidad'].dropna().mean()
            viento_gen_dir = df_sat_window['viento_direccion'].dropna().mean()
            
            # Valores de respaldo si todo el dia fuese nulo
            if np.isnan(viento_gen_vel): viento_gen_vel = 0
            if np.isnan(viento_gen_dir): viento_gen_dir = 0

            # Si la estación existe en nuestro mapa, guardamos sus datos
            if id_num in DICC_ESTACIONES and not np.isnan(media_valor):
                registros_estaciones.append({
                    "nombre_estacion": DICC_ESTACIONES[id_num]["nombre"],
                    "latitud": DICC_ESTACIONES[id_num]["lat"],
                    "longitud": DICC_ESTACIONES[id_num]["lon"],
                    contaminante: media_valor,
                    "viento_velocidad": viento_gen_vel,
                    "viento_direction": viento_gen_dir
                })
                
    return pd.DataFrame(registros_estaciones)



def generar_mapa_estaciones(df_dia, capa_pollutant):
    """
    Genera un mapa con las estaciones de medición de Madrid pintadas 
    según el nivel de contaminación para el día seleccionado.
    df_dia: DataFrame filtrado para esa fecha específica que contenga:
            'latitud', 'longitud', 'nombre_estacion' y el valor del contaminante.
    """
    # 1. Crear el mapa base centrado en Madrid (idéntico al de Copernicus)
    coordenadas_madrid = [40.416775, -3.703790]
    m = folium.Map(location=coordenadas_madrid, zoom_start=11, tiles="OpenStreetMap")
    
    # Si el dataframe del día está vacío, devolvemos el mapa base limpio
    if df_dia.empty:
        return m

    # 2. Función interna para aplicar la misma escala de colores que el Evalscript V3
    # Adaptado a los valores típicos terrestres de NO2 (µg/m³)
    def obtener_color_terrestre(valor):
        if valor is None or str(valor) == 'nan':
            return '#808080' # Gris si no hay datos
        # Escala de umbrales en µg/m³ (puedes ajustar estos límites según tus datos)
        if valor <= 20:  return '#000080'  # Azul oscuro (Limpio)
        if valor <= 40:  return '#0080FF'  # Azul claro / Cian
        if valor <= 60:  return '#00FF00'  # Verde (Moderado)
        if valor <= 80:  return '#FFFF00'  # Amarillo
        if valor <= 100: return '#FFA500'  # Naranja
        return '#FF0000'                   # Rojo (Muy Alto - Supera límite)

    # 3. Recorrer las estaciones presentes en tu dataset y dibujarlas
    for _, fila in df_dia.iterrows():
        lat = fila['latitud']
        lon = fila['longitud']
        nombre = fila['nombre_estacion']
        valor_medido = fila[capa_pollutant] # El valor de NO2, O3, etc.
        
        color_estacion = obtener_color_terrestre(valor_medido)
        
        # Formatear el texto flotante (Popup) al hacer clic en la estación
        texto_popup = f"""
        <div style="font-family: sans-serif; font-size: 12px;">
            <b>Estación:</b> {nombre}<br>
            <b>{capa_pollutant}:</b> {valor_medido:.2f} µg/m³
        </div>
        """
        
        # Dibujar el entorno de influencia de la estación
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,  # Tamaño del círculo que representa el entorno
            popup=folium.Popup(texto_popup, max_width=200),
            color="#333333",
            fill=True,
            fill_color=color_estacion,
            fill_opacity=0.9,
            weight=1.5
        ).add_to(m)
        
        vel_viento = fila.get('viento_velocidad', 0)
        dir_viento = fila.get('viento_direction', 0) # En grados (0-360)

        if vel_viento > 0:
            # El angulo meteorologico viene de donde viene el viento, 
            # invertimos para mostrar hacia donde va
            angulo_rad = math.radians(dir_viento + 180)
            angulo_grados = dir_viento + 180
            
            # Calculamos un punto final para la flecha según la velocidad
            escala = 0.002 * vel_viento 
            lat_fin = lat + (escala * math.cos(angulo_rad))
            lon_fin = lon + (escala * math.sin(angulo_rad))
            
            # Dibujamos la linea del viento sobre la estacion
            folium.PolyLine(
                locations=[[lat, lon], [lat_fin, lon_fin]],
                color="#770A32",
                weight=2,
                opacity=0.8,
                tooltip=f"Viento: {vel_viento:.1f} m/s ({dir_viento}º)"
            ).add_to(m)

            # Dibujamos la punta de la flecha (triangulo apuntando en la direccion del viento)
            # RegularPolygonMarker rota los poligonos en sentido horario empezando hacia arriba
            folium.RegularPolygonMarker(
                location=[lat_fin, lon_fin],
                number_of_sides=3,  # Un poligono de 3 lados es un triangulo
                radius=5,  # Tamaño de la punta de la flecha
                rotation=angulo_grados,  # Orientacion exacta en grados
                color="#4A5568",
                fill=True,
                fill_color="#4A5568",
                fill_opacity=0.9,
                tooltip=f"Viento: {vel_viento:.1f} m/s ({dir_viento:.0f}º)"
            ).add_to(m)

    # 4. Añadimos la misma leyenda compacta para mantener la coherencia visual
    macro_leyenda = """
    <div style="
        position: fixed; 
        bottom: 25px; left: 20px; width: 130px; height: 105px; 
        background-color: rgba(255, 255, 255, 0.9); z-index:9999; font-size:10px;
        border:1px solid #cccccc; border-radius:4px; padding: 6px 8px;
        box-shadow: 1px 1px 4px rgba(0,0,0,0.2); font-family: sans-serif;
    ">
    <b style="font-size: 11px; display: block; margin-bottom: 5px;">Medición Tierra</b>
    <div style="margin-bottom: 3px;"><i style="background: #FF0000; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Alta</div>
    <div style="margin-bottom: 3px;"><i style="background: #FFA500; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media-Alta</div>
    <div style="margin-bottom: 3px;"><i style="background: #00FF00; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media</div>
    <div style="margin-bottom: 5px;"><i style="background: #000080; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Baja</div>
    <div style="color: #666666; font-size: 8px; border-top: 1px solid #eeeeee; padding-top: 3px;">
        Valores en µg/m³
    </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(macro_leyenda))
    
    return m


def generar_mapa_contaminacion_2(fecha, capa, instance_id):
    # CHIVATO 1: Ver si la función llega a ejecutarse
    print("\n=== [PAQUETE] Iniciando generar_mapa_contaminacion ===")
    print(f"-> Fecha recibida: {fecha} (Tipo: {type(fecha)})")
    print(f"-> Capa recibida: {capa}")
    print(f"-> Instance ID: {instance_id}")

    coordenadas_madrid = [40.416775, -3.703790]
    m = folium.Map(location=coordenadas_madrid, zoom_start=11, tiles="OpenStreetMap")
    
    # 🟢 1. CONFIGURACIÓN DINÁMICA POR CONTAMINANTE (Mapeos y Leyendas)
    capa_upper = str(capa).upper().replace(".", "_") # Estandariza PM2.5 o PM2_5 a PM2_5
    
    # Valores por defecto
    nombre_display = capa_upper
    unidades_leyenda = "Valores de Satélite"
    color_alta = "#FF0000"  # Rojo
    color_baja = "#000080"  # Azul oscuro
    extra_params = ""       # Para añadir scripts de ganancia/escala si fuera necesario en la URL
    
    if "NO2" in capa_upper:
        nombre_display = "NO₂"
        unidades_leyenda = "Valores: 10⁻⁴ mol/m²"
        color_alta = "#FF0000"
        color_baja = "#000080"
        capa_wms = "NO2"
    elif "O3" in capa_upper or "OZONE" in capa_upper:
        nombre_display = "Ozono (O₃)"
        unidades_leyenda = "Valores: Unidades Dobson"
        # 🟢 Solución al mapa rojo: Usamos una paleta alternativa como Viridis o Plasma en tu panel,
        # o reajustamos la percepción visual en la leyenda (Baja suele ser púrpura/azul, Alta amarillo/rojo)
        color_alta = "#FDE725" # Amarillo brillante (típico de escalas de Ozono como Viridis)
        color_baja = "#440154" # Púrpura oscuro
        capa_wms = "O3"
    elif "PM10" in capa_upper:
        nombre_display = "PM₁₀"
        unidades_leyenda = "Estimación: µg/m³"
        color_alta = "#990000"
        color_baja = "#E2E8F0"
    elif "PM2" in capa_upper:
        nombre_display = "PM₂.₅"
        unidades_leyenda = "Estimación: µg/m³"
        color_alta = "#742A2A"
        color_baja = "#EDF2F7"

    # Forzar la conversión de fecha a texto pase lo que pase
    if fecha is not None and fecha != "":
        if not isinstance(fecha, str):
            fecha_str = fecha.strftime("%Y-%m-%d")
        else:
            fecha_str = fecha
            
        print(f"-> Entrando al bloque de renderizado para la fecha: {fecha_str}")
        
        bbox_madrid = "-4.25,39.85,-3.05,41.20"
        
        # URL base de tu panel de Copernicus
        url_base_panel = "https://sh.dataspace.copernicus.eu/ogc/wms/aebfda82-f506-448c-9b32-265088990cfd"
        
        # 2. Le concatenamos los parámetros de la petición de la imagen
        url_copernicus = (
            f"{url_base_panel}"
            f"?service=WMS"
            f"&version=1.1.1"
            f"&request=GetMap"
            f"&layers={capa_wms}"  # Mantiene la capa exacta solicitada por el selector (ej: O3, NO2...)
            f"&format=image/png"
            f"&transparent=true"
            f"&time={fecha_str}"
            f"&srs=EPSG:4326"
            f"&bbox={bbox_madrid}"
            f"&width=600"
            f"&height=400"
        )
        print(f"-> URL GENERADA: {url_copernicus}")
        
        # Añadir la capa al mapa
        try:
            ImageOverlay(
                image=url_copernicus,
                bounds=[[39.85, -4.25], [41.20, -3.05]],
                opacity=0.3,
                name=f"Copernicus {nombre_display}",
                interactive=True,
                cross_origin=False
            ).add_to(m)
            print(f"-> [ÉXITO] ImageOverlay para {nombre_display} añadido correctamente")
        except Exception as e:
            print(f"-> [ERROR] Falló al añadir el ImageOverlay: {e}")
            
    else:
        print("-> [ALERTA] La fecha llegó vacía (None o ''), saltándose la capa de satélite.")
        
    print("=== [PAQUETE] Fin de la función, retornando mapa ===\n")

    # 🟢 2. CREACIÓN DE LEYENDA DINÁMICA UTILIZANDO F-STRINGS
    macro_leyenda = f"""
        <div style="
            position: fixed; 
            bottom: 25px; left: 20px; width: 130px; height: 105px; 
            background-color: rgba(255, 255, 255, 0.9); z-index:9999; font-size:10px;
            border:1px solid #cccccc; border-radius:4px; padding: 6px 8px;
            box-shadow: 1px 1px 4px rgba(0,0,0,0.2); font-family: sans-serif;
        ">
        <b style="font-size: 11px; display: block; margin-bottom: 5px;">Nivel de {nombre_display}</b>
        <div style="margin-bottom: 3px;"><i style="background: {color_alta}; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Alta</div>
        <div style="margin-bottom: 3px;"><i style="background: #FFA500; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media-Alta</div>
        <div style="margin-bottom: 3px;"><i style="background: #00FF00; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media</div>
        <div style="margin-bottom: 5px;"><i style="background: {color_baja}; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Baja</div>
        <div style="color: #666666; font-size: 8px; border-top: 1px solid #eeeeee; padding-top: 3px;">
            {unidades_leyenda}
        </div>
        </div>
        """
        
    # Añadimos la leyenda dinámica al mapa de Folium
    m.get_root().html.add_child(folium.Element(macro_leyenda))
    
    return m

from folium.plugins import HeatMap


def generar_mapa_contaminacion3(fecha, capa, instance_id, df_historico=None):
    """
    Genera el mapa de Folium combinando la capa OGC de Copernicus (satélite)
    con una capa superpuesta de Mapa de Calor (HeatMap) basada en los datos de las estaciones en tierra.
    """
    print("\n=== [PAQUETE] Iniciando generar_mapa_contaminacion ===")
    
    coordenadas_madrid = [40.416775, -3.703790]
    m = folium.Map(location=coordenadas_madrid, zoom_start=11, tiles="OpenStreetMap")
    
    capa_str = str(capa).upper().replace(".", "_") 
    
    # 1. Configuración de nombres y estilos de la leyenda (Igual que antes)
    nombre_display = capa_str
    unidades_leyenda = "Valores de Satélite"
    color_alta = "#FF0000"
    color_baja = "#000080"
    columna_df_contaminante = "" # Para buscar en tu dataframe terrestre
    
    if "NO2" in capa_str:
        nombre_display = "NO₂"
        unidades_leyenda = "Valores: 10⁻⁴ mol/m²"
        capa_wms = "NO2"
        columna_df_contaminante = "no2" # Ajusta al nombre real de tu columna
    elif "O3" in capa_str or "OZONE" in capa_str:
        nombre_display = "Ozono (O₃)"
        unidades_leyenda = "Valores: mol/m² (0.13 - 0.16)"
        color_alta = "#FDE725"
        color_baja = "#440154"
        capa_wms = "O3"
        columna_df_contaminante = "o3"
    elif "PM10" in capa_str:
        nombre_display = "PM₁₀"
        unidades_leyenda = "Estimación satélite / Estaciones terrestres"
        capa_wms = "AER_AI" # Usamos índice de aerosoles si no hay capa PM directa
        columna_df_contaminante = "pm10"
    elif "PM2" in capa_str:
        nombre_display = "PM₂.₅"
        unidades_leyenda = "Estimación satélite / Estaciones terrestres"
        capa_wms = "AER_AI"
        columna_df_contaminante = "pm2_5"

    # Forzar la conversión de fecha a texto
    if fecha is not None and fecha != "":
        if not isinstance(fecha, str):
            fecha_str = fecha.strftime("%Y-%m-%d")
        else:
            fecha_str = fecha
            
        bbox_madrid = "-4.25,39.85,-3.05,41.20"
        url_base_panel = "https://sh.dataspace.copernicus.eu/ogc/wms/aebfda82-f506-448c-9b32-265088990cfd"
        
        url_copernicus = (
            f"{url_base_panel}?service=WMS&version=1.1.1&request=GetMap"
            f"&layers={capa_wms}&format=image/png&transparent=true"
            f"&time={fecha_str}&srs=EPSG:4326&bbox={bbox_madrid}&width=600&height=400"
        )
        
        # --- CAPA 1: Satélite Copernicus (Fondo) ---
        try:
            ImageOverlay(
                image=url_copernicus,
                bounds=[[39.85, -4.25], [41.20, -3.05]],
                opacity=0.3, # Opacidad baja para que se vea el mapa base y el heatmap
                name=f"Satélite: {nombre_display}",
                interactive=True,
                cross_origin=False
            ).add_to(m)
        except Exception as e:
            print(f"-> [ERROR] Falló al añadir Copernicus: {e}")
            
        # --- CAPA 2: Mapa de Calor Terrestre (Superpuesta) ---
        # Verificamos que nos pases el dataframe y que la columna exista
        if df_historico is not None and columna_df_contaminante in df_historico.columns:
            
            # Filtramos el dataframe terrestre para quedarnos SOLO con el día activo
            # Asegúrate de que la columna 'timestamp' coincida con el formato de fecha_str
            df_dia = df_historico[pd.to_datetime(df_historico['timestamp']).dt.date == pd.to_datetime(fecha_str).date()]
            
            puntos_calor = []
            
            # Iteramos sobre tus estaciones guardadas en tu diccionario global DICC_ESTACIONES
            for id_est, info in DICC_ESTACIONES.items():
                col_estacion = f"estacion_id_{id_est}"
                
                if col_estacion in df_dia.columns:
                    # Filtramos las filas del día donde esa estación estuvo activa (one-hot == 1)
                    df_estacion_dia = df_dia[df_dia[col_estacion] == 1]
                    
                    if not df_estacion_dia.empty:
                        # Sacamos la media de contaminación de ese día para esa estación
                        media_valor = df_estacion_dia[columna_df_contaminante].mean()
                        
                        # Si el valor es válido, lo añadimos: [lat, lon, peso_del_calor]
                        if pd.notna(media_valor) and media_valor > 0:
                            puntos_calor.append([info['lat'], info['lon'], media_valor])
            
            # Si hemos recolectado puntos, dibujamos el mapa de calor encima
            if puntos_calor:
                HeatMap(
                    data=puntos_calor,
                    radius=25,       # Radio de influencia de cada estación en píxeles
                    blur=15,         # Suavizado de los bordes del mapa de calor
                    min_opacity=0.3, # Visibilidad mínima en el centro del foco
                    name="Estaciones: Inmisión Real"
                ).add_to(m)
                print(f"-> [ÉXITO] HeatMap superpuesto para {columna_df_contaminante} con {len(puntos_calor)} puntos.")

    # Control de capas nativo de Folium para que el usuario pueda activar/desactivar la que quiera
    folium.LayerControl().add_to(m)

    # 3. Leyenda dinámica (Igual que tenías)
    macro_leyenda = f"""
        <div style="
            position: fixed; 
            bottom: 25px; left: 20px; width: 130px; height: 105px; 
            background-color: rgba(255, 255, 255, 0.9); z-index:9999; font-size:10px;
            border:1px solid #cccccc; border-radius:4px; padding: 6px 8px;
            box-shadow: 1px 1px 4px rgba(0,0,0,0.2); font-family: sans-serif;
        ">
        <b style="font-size: 11px; display: block; margin-bottom: 5px;">Nivel de {nombre_display}</b>
        <div style="margin-bottom: 3px;"><i style="background: {color_alta}; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Alta</div>
        <div style="margin-bottom: 3px;"><i style="background: #FFA500; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media-Alta</div>
        <div style="margin-bottom: 3px;"><i style="background: #00FF00; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Media</div>
        <div style="margin-bottom: 5px;"><i style="background: {color_baja}; width: 14px; height: 10px; float: left; margin-right: 6px; border-radius:1px;"></i>Baja</div>
        <div style="color: #666666; font-size: 8px; border-top: 1px solid #eeeeee; padding-top: 3px;">
            {unidades_leyenda}
        </div>
        </div>
        """
    m.get_root().html.add_child(folium.Element(macro_leyenda))
    
    return m