import streamlit as st
import joblib
import urllib.request
import os
import pandas as pd
import altair as alt
from sqlalchemy import text
import folium
from streamlit_folium import st_folium
from ui import tab_historico, tab_prediccion, tab_historico_todas
from datetime import datetime, timedelta
import core.model_configs as mc

# Limites legales:
limites_contaminantes = {'no2':40,'o3':120,'pm10':50}

# 1. Diccionario de estaciones
mapa_estaciones = {
    4: 'Plaza de España', 8: 'Escuelas Aguirre', 16: 'Arturo Soria',
    18: 'Farolillo', 24: 'Casa de Campo', 35: 'Plaza del Carmen',
    36: 'Moratalaz', 38: 'Cuatro Caminos', 39: 'Barrio del Pilar',
    54: 'Ensanche de Vallecas', 56: 'Plaza Elíptica', 58: 'El Pardo', 
    59: 'Juan Carlos I'
}

# 1. Configuración de la página (¡Debe ser lo primero!)
st.set_page_config(
    page_title="Calidad del Aire - Madrid",
    page_icon="😷",
    layout="wide"
)

def main():
    
    # 2. Título y Cabecera Principal
    st.title("📊 Monitor de Calidad del Aire en Madrid")
    st.markdown("""
    Esta aplicación modular muestra datos históricos y predicciones de contaminación
    para las próximas 24 horas en la ciudad de Madrid.
    """)
    st.divider()
    
    st.sidebar.header("Filtros globales")
        # Selector de contaminante
    pollutant_sel = st.sidebar.selectbox(
            "Selecciona el Contaminante", 
            mc.CONTAMINANTES_DISPONIBLES,
            key="hist_pollutant"
        )

    codigos_validos = [
        cod for cod, info in mc.ESTACIONES_MADRID.items() 
        if pollutant_sel in info["contaminantes"]
        ]

    codigo_sel = st.sidebar.selectbox(
            "Selecciona la Estación",
            options=codigos_validos,
            format_func=lambda x: mc.ESTACIONES_MADRID[x]["nombre"],
            help="Solo se muestran estaciones que miden el gas seleccionado.",
            key="hist_estacion"
        )
    st.sidebar.subheader("Rango de fechas")
    fecha_inicio = st.sidebar.date_input(
            "Fecha inicio", 
            #value=datetime.now() - timedelta(days=7),
            value=datetime(2021, 3, 1),
            max_value=datetime.now(),
            key="hist_f_inicio"
        )
    fecha_fin = st.sidebar.date_input(
            "Fecha fin", 
            #value=datetime.now(),
            value=datetime(2021, 3, 8),
            max_value=datetime.now(),
            key="hist_f_fin"
        )
        # Validación básica de fechas
    if fecha_inicio > fecha_fin:
        st.error("Error: La fecha de inicio debe ser anterior a la fecha de fin.")
        return

    opciones_meteo = {
        "Viento (km/h)": "viento_velocidad",
        "Temperatura (°C)": "temperatura",
        "Humedad (%)": "humedad",
        "Presión (hPa)": "presion",
        "Radiación Solar": "radiacion_solar",
        "Intensidad Trafico (veh/h)": "intensidad"
        }

    seleccionados = st.sidebar.multiselect(
        "Selecciona qué parámetros meteorológicos mostrar:",
        options=list(opciones_meteo.keys()),
        default=["Viento (km/h)", "Temperatura (°C)"] # Valores por defecto
        )

    # 3. Creación de las Pestañas (Tabs)
    tab1, tab2, tab3 = st.tabs(["🕒 Datos Históricos","Histórico Global", "🔮 Predicción 24h"])

    # 4. Renderizado del contenido de cada pestaña usando los módulos de 'ui'
    with tab1:
        tab_historico.render_content(pollutant_sel,codigo_sel,fecha_inicio,fecha_fin,seleccionados,opciones_meteo)
    with tab2:
        tab_historico_todas.render_content(pollutant_sel,codigo_sel,fecha_inicio,fecha_fin,seleccionados)
    with tab3:
        tab_prediccion.render_content(pollutant_sel,codigo_sel,fecha_inicio,fecha_fin,seleccionados)

if __name__ == "__main__":
    main()