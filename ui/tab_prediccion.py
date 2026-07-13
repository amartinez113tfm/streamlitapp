# ui/tab_prediccion.py
import streamlit as st
#from core import data_manager, model_handler
import plotly.graph_objects as go
import datetime
from predictores import no2,o3
from core import data_manager as dm
from ui import components as co
from utils import constants as cte
import pandas as pd
import utils.constants as cte

def render_content(pollutant_sel,codigo_sel,fecha_inicio,fecha_fin,seleccionados):
    st.header("Predicciones para las Próximas 24 Horas")

       # --- 3. EL BOTÓN DE EJECUCIÓN EN STREAMLIT ---
    # El codigo dentro de este 'if' solo se ejecuta al pulsar el boton
    # Componente visual para que el usuario elija la estacion por su nombre
    estacion_seleccionada = st.selectbox(
        "Selecciona la estación de monitorización:",
        options=list(cte.mapa_estaciones_O3.keys()),
        index=0  # Por defecto aparecera seleccionada Escuelas Aguirre (ID: 8)
    )

    # Obtenemos el ID en formato string correspondiente para pasarselo a tus funciones
    id_estacion_str = cte.mapa_estaciones_O3[estacion_seleccionada]
    if st.button("Calcular Previsión de Ozono para las próximas 24 horas", type="primary"):
            
            with st.spinner("Conectando a las colecciones de MongoDB y unificando historicos..."):
                # Llamamos a tu funcion
                #df_bloque_pasado = o3.extraer_bloque_24h_consistente("8")
                df_bloque_pasado = o3.bloque48hCiclicas(id_estacion_str)
            if df_bloque_pasado is None or len(df_bloque_pasado) < 48:
                st.error(f"No se han podido reunir 48 horas consecutivas completas para la estación. Verifica las bases de datos.")
            else:
                st.success(f"¡Datos de las últimas 48 horas cargados con éxito! (Ventana temporal: {df_bloque_pasado['timestamp'].min()} a {df_bloque_pasado['timestamp'].max()})")
                
                # Mostramos una vista previa de la tabla unificada para que el tribunal del TFM vea que es real
                with st.expander("Ver matriz de entrada unificada (Últimas 24h medidass)"):
                    st.dataframe(df_bloque_pasado)

                co.graficos_24horas(df_bloque_pasado)
                #o3.prediccionO3HF(df_bloque_pasado,'8')
                o3.prediccionReal48h_3(df_bloque_pasado,id_estacion_str)

                
    if st.button("Prueba Previsión para las próximas 24 horas", type="primary"):
        o3.prueba24Horas(id_estacion_str)
    
    with st.spinner("Consultando datos..."):
        #df = dm.get_historical_data(codigo_sel, pollutant_sel,fecha_inicio,fecha_fin)
        #df = dm.get_combined_data(codigo_sel, pollutant_sel, fecha_inicio, fecha_fin)
        df = dm.get_datos_parquetTotal(codigo_sel, pollutant_sel,fecha_inicio,fecha_fin)

    with st.spinner("Haciendo Predicciones..."):
            #df = dm.get_historical_data(codigo_sel, pollutant_sel,fecha_inicio,fecha_fin)
            #df_all = dm.get_all_contaminants_monthly(pollutant_sel)
        df_resultados=no2.render_prediction_tab(df,fecha_inicio,fecha_fin)
        #st.dataframe(df_resultados.head(5))
        #render_residuals_chart(df)
        no2.render_error_metrics(df)
    # 3. Visualización
        
        # Llamada a la función que combina todo
        #df = dm.get_combined_data(codigo_sel, pollutant_sel, fecha_inicio, fecha_fin)

        

        # Supongamos que ya tienes el df_filtrado y el limite
        cm = dm.obtener_matriz_confusion(df, 'no2', 40)

        st.subheader("Matriz de Confusion: Superacion de Limites")

        
        colMC, colOtra  = st.columns(2)
        with colMC:
            fig_plotly = co.dibujar_matriz_plotly(cm, cte.UMBRALES[pollutant_sel.lower()])
            st.plotly_chart(fig_plotly, use_container_width=True)
            return
        with colOtra:  
            # En tu Streamlit:
            #fig_scatter = dibujar_scatter_rendimiento(df, 'no2', 'NO2')
            #st.plotly_chart(fig_scatter, use_container_width=True) # Mantener False para respetar el tamaño
            st.dataframe(df.head(2))

 