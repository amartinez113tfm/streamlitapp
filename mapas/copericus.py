import streamlit as st
import folium
from streamlit_folium import st_folium
from datetime import datetime, date
from folium.raster_layers import ImageOverlay


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



'''
def generar_mapa_contaminacion(fecha, capa, instance_id):
    coordenadas_madrid = [40.416775, -3.703790]
    m = folium.Map(location=coordenadas_madrid, zoom_start=10, tiles="OpenStreetMap")
    
    if fecha:
        # SI ES UN TEXTO: Lo convertimos a un objeto fecha real
        if isinstance(fecha, str):
            # Adapta el formato '%Y-%m-%d' si tu texto viene separado de otra forma (ej. '%d/%m/%Y')
            fecha_objeto = datetime.strptime(fecha, "%Y-%m-%d").date()
        else:
            fecha_objeto = fecha

        # Ahora ya es seguro usar strftime porque garantizamos que es un objeto fecha
        fecha_str = fecha_objeto.strftime("%Y-%m-%d")
        # Esto cubre perfectamente la Comunidad de Madrid
        bbox_madrid = "39.85,-4.25,41.20,-3.05"

        #wms_url = f"https://sh.dataspace.copernicus.eu/ogc/wms/{instance_id}"
        url_copernicus = (
            f"https://sh.dataspace.copernicus.eu/ogc/wms/{instance_id}"
            f"?service=WMS"
            f"&version=1.1.1"
            f"&request=GetMap"
            f"&layers={capa}"
            f"&format=image/png"
            f"&transparent=true"
            f"&time={fecha_str}"
            f"&srs=EPSG:4326"  # Usamos el sistema estándar que Copernicus entiende sin fallos
            f"&bbox={bbox_madrid}"
            f"&width=800"
            f"&height=600"
        )
        
        folium.WmsTileLayer(
            url=wms_url,
            layers=capa,
            fmt="image/png",
            transparent=True,
            version="1.1.1",
            srs="EPSG:3857",
            time=fecha_str,
            overlay=True
        ).add_to(m)
        
        # 4. Superponemos la imagen directamente sobre el mapa
        ImageOverlay(
            image=url_copernicus,
            bounds=[[39.85, -4.25], [41.20, -3.05]], # Mismos límites geográficos
            opacity=0.6,
            name=f"Contaminacion {fecha_str}",
            interactive=True,
            cross_origin=False # Esto fulmina el CORB del navegador definitivamente
        ).add_to(m)

    return m  # ¡CRUCIAL: retornar el objeto mapa!
    '''


def generar_mapa_contaminacion(fecha, capa, instance_id):
    # CHIVATO 1: Ver si la función llega a ejecutarse
    print("\n=== [PAQUETE] Iniciando generar_mapa_contaminacion ===")
    print(f"-> Fecha recibida: {fecha} (Tipo: {type(fecha)})")
    print(f"-> Capa recibida: {capa}")
    print(f"-> Instance ID: {instance_id}")

    coordenadas_madrid = [40.416775, -3.703790]
    m = folium.Map(location=coordenadas_madrid, zoom_start=12, tiles="OpenStreetMap")
    
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