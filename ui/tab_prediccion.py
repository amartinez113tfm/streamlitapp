# ui/tab_prediccion.py
import streamlit as st
#from core import data_manager, model_handler
import plotly.graph_objects as go
import datetime

def render_content(pollutant_sel,codigo_sel,fecha_inicio,fecha_fin,seleccionados):
    st.header("Predicciones para las Próximas 24 Horas")