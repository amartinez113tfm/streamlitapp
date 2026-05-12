import streamlit as st
import pandas as pd
from core import data_manager as dm
import ui.components as co
import core.model_configs as mc


def render_content(pollutant_sel,codigo_sel,fecha_inicio,fecha_fin,seleccionados):
    
    df_total = dm.get_todo()
    #st.dataframe(df_total.head(5))
    st.title("📊 Análisis Global de la Red")

  
    co.render_historical_candlestick_trimestral(df_total,pollutant_sel)
    
    co.render_ridge_plot(df_total,pollutant_sel)


    col1,col2,col3 = st.columns([1,2,1])
    with col2:
        co.render_historical_trends_chart_2(df_total,pollutant_sel)
    