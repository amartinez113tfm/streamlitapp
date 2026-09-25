import streamlit as st
import pandas as pd
from core import data_manager as dm
import ui.components as co
import core.model_configs as mc
import mapas.copericus as cop
from streamlit_folium import st_folium
import datetime
import altair as alt
from utils import constants as cte

# 1. Inicializar las coordenadas por defecto en el estado de la sesion si no existen
if "map_center" not in st.session_state:
    st.session_state["map_center"] = [40.416775, -3.703790]
if "map_zoom" not in st.session_state:
    st.session_state["map_zoom"] = 10



def render_content():
    
    df_total = dm.get_todo()
    #st.dataframe(df_total.head(5))
    st.title("📊 Análisis Global de la Red")

  
    
    

    '''
    mapa_contaminacion=cop.generar_mapa_contaminacion('2026-02-15','NO2',instance_id=st.secrets['COPERNICUS_ID'])
    if mapa_contaminacion:
        st_data = st_folium(mapa_contaminacion, width=600, height=400)
    
    col1,col2,col3 = st.columns([1,2,1])
    with col2:
        #co.render_historical_trends_chart_2(df_total,pollutant_sel)
    '''    
    


    # --- EN TU INTERFAZ (tab_historico_todas.py) ---
    with st.form(key="formCopernicus"):
        st.subheader("📊 Comparativa Síncrona: Satélite vs. Datos Terrestres")

        colFecha,colContaminante = st.columns(2) 
        with colFecha:
            # 1. Creamos un único selector de fecha para ambos mapas
            # Puedes ajustar la fecha por defecto (aquí ponemos el 15 de mayo de 2026 como ejemplo)
            fecha_seleccionada = st.date_input(
                "Selecciona la fecha para el análisis:",
                value=datetime.date(2025, 5, 15),
                min_value=datetime.date(2018, 1, 1), # Sentinel-5P tiene datos desde 2018 aprox.
                max_value=datetime.date.today(),
                key='fechaSelNew'
            )
        with colContaminante:
            # Selector de contaminante (por si quieres alternar entre NO2, O3, etc.)
            pollutant_sel = st.selectbox(
                "Selecciona el contaminante a visualizar:",
                options=["NO2", "O3", "PM10","PM2_5"],
                index=0,
                key='polulantSelNew'
            )

        # 2. Convertimos la fecha a string para la API de Copernicus
        fecha_str = fecha_seleccionada.strftime("%Y-%m-%d")
        submitted = st.form_submit_button(
                                        "🔄 Aplicar Filtros y Actualizar Gráficas",
                                        use_container_width=True,
                                    )   
        # Generamos el dataframe transformado y sincronizado en hora
        with st.spinner("Conectando con Copernicus y procesando datos meteorológicos de Madrid..."):
            df_tierra_listo = cop.obtener_datos_tierra_sincronizados(df_total, fecha_seleccionada, pollutant_sel)


            # 2. Generar los mapas base usando las coordenadas del estado actual
            mapa_satelite = cop.generar_mapa_contaminacion(fecha_str, pollutant_sel, st.secrets["COPERNICUS_ID"])
            mapa_tierra = cop.generar_mapa_estaciones(df_tierra_listo, pollutant_sel)

            # Sobrescribir el zoom y centro antes de pintarlos para asegurar unificado total
            #mapa_satelite.location = st.session_state["map_center"]
            #mapa_satelite.zoom_start = st.session_state["map_zoom"]
            #mapa_tierra.location = st.session_state["map_center"]
            #mapa_tierra.zoom_start = st.session_state["map_zoom"]
            
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 🛰️ Capa de Satélite (Copernicus S5P)")
                # Muestra la ventana de paso estimada en la UI para justificar el rigor de tu TFM
                st.caption("⏱️ Ventana de captura satelital: ~13:00 - 15:00 UTC")
                #mapa_satelite = cop.generar_mapa_contaminacion(fecha_str, pollutant_sel, st.secrets["COPERNICUS_ID"])
        
                st_data_sat=st_folium(mapa_satelite, width=540, height=450, key="mapa_sat_key_new")

            with col2:
                st.markdown("#### 📍 Estaciones en Tierra")
                st.caption("⏱️ Media calculada para el intervalo de paso del satélite")
                
                if df_tierra_listo.empty:
                    st.warning("Sin registros terrestres coincidentes.")
                    mapa_tierra_vacio = cop.generar_mapa_estaciones(df_tierra_listo, pollutant_sel)
                    st_folium(mapa_tierra_vacio, width=540, height=450, key="mapa_vacio_key_new")
                else:
                    #mapa_tierra = cop.generar_mapa_estaciones(df_tierra_listo, pollutant_sel)
                    st_data_tie=st_folium(mapa_tierra, width=540, height=450, key="mapa_tie_key_new")

         

        #Descomentar cuando salga bien el mapa
        #co.render_ridge_plot(df_total,pollutant_sel)
    
    #co.render_historical_candlestick_trimestral(df_total,pollutant_sel)
   
    

    '''
    df_final = df_total[df_total['estacion_id_24'] == 1]
    st.altair_chart(alt.Chart(df_final).mark_rect().encode(
        alt.X('o3:Q').bin(maxbins=40),
        alt.Y('no2:Q').bin(maxbins=60),
        alt.Color('count():Q').scale(scheme='greenblue')))
    '''
    df_superaciones_totales = dm.calcular_superaciones_anuales(df_total)
    #st.dataframe(df_superaciones_totales[df_superaciones_totales['Veces Superado']>0])
    
    df_superaciones_ready = df_superaciones_totales[
    (df_superaciones_totales['Veces Superado'] > 0) &
    (df_superaciones_totales['Contaminante'] == pollutant_sel.upper())
    ]

    #st.dataframe(df_superaciones_ready.head())
    #co.render_historical_overages_chart(df_superaciones_ready,pollutant_sel)
    
    st.subheader(f"📊 Evolución histórica de {pollutant_sel.upper()} y superaciones límites")
    
    
    

    

        # --- Dentro de ui/tab_historico_todas.py ---
    
    # 1. Generamos el objeto del gráfico y su objeto de selección
    chart_objeto, selector_clic = co.render_historical_overages_trends_3(df_superaciones_ready, pollutant_sel)

    if chart_objeto is not None:
        
        # 🟢 CREAMOS TRES COLUMNAS EN LA MISMA LÍNEA HORIZONTAL
        # El primer gráfico y el segundo se llevan más peso (3), y el dataframe un poco menos (2)
        col_grafica2,colNada, col_dataframe, colNada2 = st.columns([2,1, 3,1])
        
        
        with col_grafica2:
            st.markdown(f"📊 **Histórico de Superaciones ({pollutant_sel})**")
            evento_seleccion = st.altair_chart(chart_objeto, use_container_width=True, on_select="rerun",key="newSuperaciones")
            
        
        # --- COLUMNA 3: El DataFrame dinamico o el cartel de ayuda ---
        with col_dataframe:
            # Comprobamos si el usuario ha hecho clic en algun nodo de Altair
            datos_clicados = evento_seleccion.get("selection", {}).get("selector_clic", [])
            
            if isinstance(datos_clicados, list) and len(datos_clicados) > 0:
                
                # Extraemos las variables del nodo seleccionado
                anio_clicado = datos_clicados[0].get("Año")
                estacion_clicada = datos_clicados[0].get("Estación")
                
                st.markdown(f"📋 **Días Críticos**\n*{estacion_clicada} ({anio_clicado})*")
                
                # --- Proceso de filtrado de tu df_total ---
                df_original_copia = df_total.copy()
                df_original_copia['Anio'] = pd.to_datetime(df_original_copia['timestamp']).dt.year
                df_original_copia['Fecha'] = pd.to_datetime(df_original_copia['timestamp']).dt.date
                
                col_contaminante = pollutant_sel.lower().replace(".", "_")
                
                id_estacion_activa = None
                for id_est, info in cte.DICC_ESTACIONES.items():
                    if info['nombre'] == estacion_clicada:
                        id_estacion_activa = id_est
                        break
                        
                if id_estacion_activa is not None:
                    col_estacion_binaria = f"estacion_id_{id_estacion_activa}"
                    
                    # Inicializamos una variable comun para estructurar los datos de la tabla
                    df_mostrar = pd.DataFrame()
                    
                    if col_contaminante in ['pm10', 'pm2_5']:
                        limite_valor = 15 if col_contaminante == 'pm2_5' else 50
                        df_est_anio = df_original_copia[(df_original_copia['Anio'] == anio_clicado) & (df_original_copia[col_estacion_binaria] == 1)]
                        dias_infractores = df_est_anio.groupby('Fecha')[col_contaminante].mean().reset_index()
                        df_mostrar = dias_infractores[dias_infractores[col_contaminante] > limite_valor].copy()
                        if not df_mostrar.empty:
                            df_mostrar.columns = ['Fecha', 'Media (µg/m³)']
                        
                    else:
                        limite_valor = 200 if col_contaminante == 'no2' else 180
                        horas_infractoras = df_original_copia[
                            (df_original_copia['Anio'] == anio_clicado) & 
                            (df_original_copia[col_estacion_binaria] == 1) & 
                            (df_original_copia[col_contaminante] > limite_valor)
                        ][['timestamp', col_contaminante]].copy()
                        
                        if not horas_infractoras.empty:
                            # Agrupamos u obtenemos las fechas para la visualizacion de la tabla
                            horas_infractoras['Fecha'] = pd.to_datetime(horas_infractoras['timestamp']).dt.date
                            df_mostrar = horas_infractoras[['Fecha', 'timestamp', col_contaminante]].copy()
                            df_mostrar.columns = ['Fecha', 'Fecha/Hora', 'Valor Horario']

                    # Si encontramos registros criticos, configuramos la tabla interactiva
                    if not df_mostrar.empty:
                        # 🟢 ACTIVAMOS LA INTERACTIVIDAD EN LA TABLA
                        seleccion_tabla = st.dataframe(
                            df_mostrar, 
                            use_container_width=True, 
                            hide_index=True,
                            on_select="rerun",
                            selection_mode="single-row"
                        )
                        
                        # 🟢 LEEMOS QUE FILA HA SELECCIONADO EL USUARIO EN LA TABLA
                        filas_seleccionadas = seleccion_tabla.get("selection", {}).get("rows", [])
                        
                        if filas_seleccionadas:
                            # Si el usuario hace clic en una fila, extraemos esa fecha concreta
                            indice_fila = filas_seleccionadas[0]
                            fecha_concreta = df_mostrar.iloc[indice_fila]['Fecha']
                        else:
                            # Por defecto (si no ha hecho clic aun), se analiza el primer dia de la lista
                            fecha_concreta = df_mostrar.iloc[0]['Fecha']
                            
                        # Nos aseguramos de que la variable mantenga solo el formato de tipo date
                        if not isinstance(fecha_concreta, datetime.date) and hasattr(fecha_concreta, 'date'):
                            fecha_concreta = fecha_concreta.date()
                    else:
                        st.info("No se encontraron registros que superen los limites legales.")
                        fecha_concreta = None

                    # ==============================================================================
                    # DETALLE VISUAL: MINIGRAFICAS HORARIAS
                    # ==============================================================================
                    if fecha_concreta is not None:
                        st.markdown("---")
                        st.markdown(f"### 🔍 Diagnóstico Dinámico del Incidente: **{pd.to_datetime(fecha_concreta).strftime('%d/%m/%Y')} {estacion_clicada}**")
                        st.caption(f"Análisis horario de variables exógenas registradas en la estación {estacion_clicada}")
                        
                        # 1. Filtrado por fecha y por estacion activa para limpiar duplicados
                        df_dia_completo = df_original_copia[df_original_copia['Fecha'] == fecha_concreta].copy()
                        df_dia_completo['Hora'] = pd.to_datetime(df_dia_completo['timestamp']).dt.hour
                        df_dia_completo = df_dia_completo[df_dia_completo[col_estacion_binaria] == 1]
                        
                        # Preparamos las columnas numericas existentes para evitar fallos de clave
                        columnas_interes = ['Hora', col_contaminante]
                        if 'intensidad' in df_dia_completo.columns:
                            columnas_interes.append('intensidad')
                        if 'temperatura' in df_dia_completo.columns:
                            columnas_interes.append('temperatura')
                            
                        # Reducimos los datos a 24 puntos limpios calculando la media horaria
                        df_dia_render = df_dia_completo[columnas_interes].groupby('Hora').mean().reset_index()
                        
                        # 2. Render de las 3 minigraficas en paralelo
                        col_exog1, col_exog2, col_exog3 = st.columns(3)
                        
                        # --- GRAFICA A: Trafico ---
                        with col_exog1:
                            st.markdown("🚗 **Evolución del Tráfico Urbano**")
                            if 'intensidad' in df_dia_render.columns:
                                chart_trafico = alt.Chart(df_dia_render).mark_area(
                                    line={'color': '#1f77b4'},
                                    color=alt.Gradient(
                                        gradient='linear',
                                        stops=[alt.GradientStop(color='#1f77b4', offset=0),
                                            alt.GradientStop(color='transparent', offset=1)],
                                        x1=1, x2=1, y1=1, y2=0
                                    )
                                ).encode(
                                    x=alt.X('Hora:O', title='Hora del Día'),
                                    y=alt.Y('intensidad:Q', title='Intensidad (Vehículos/h)'),
                                    tooltip=['Hora', 'intensidad']
                                ).properties(height=180)
                                st.altair_chart(chart_trafico, use_container_width=True)
                            else:
                                st.caption("No hay datos de intensidad de trafico.")
                                
                        # --- GRAFICA B: Clima ---
                        with col_exog2:
                            st.markdown("☀️ **Temperatura y Factores Climáticos**")
                            if 'temperatura' in df_dia_render.columns:
                                chart_clima = alt.Chart(df_dia_render).mark_line(
                                    color='#ff7f0e', strokeWidth=3, point=True
                                ).encode(
                                    x=alt.X('Hora:O', title='Hora del Día'),
                                    y=alt.Y('temperatura:Q', title='Temperatura (°C)'),
                                    tooltip=['Hora', 'temperatura']
                                ).properties(height=180)
                                st.altair_chart(chart_clima, use_container_width=True)
                            else:
                                st.caption("No hay datos de temperatura.")
                                
                        # --- GRAFICA C: El Contaminante ---
                        with col_exog3:
                            st.markdown(f"☣️ **Curva de Inmisión de {pollutant_sel}**")
                            if col_contaminante in df_dia_render.columns:
                                chart_gas = alt.Chart(df_dia_render).mark_line(
                                    color='#d62728', strokeWidth=3
                                ).encode(
                                    x=alt.X('Hora:O', title='Hora del Día'),
                                    y=alt.Y(f'{col_contaminante}:Q', title='Concentración (µg/m³)'),
                                    tooltip=['Hora', col_contaminante]
                                ).properties(height=180)
                                
                                linea_limite = alt.Chart(pd.DataFrame({'y': [limite_valor]})).mark_rule(
                                    color='red', strokeDash=[4, 4], strokeWidth=2
                                ).encode(y='y:Q')
                                
                                st.altair_chart(chart_gas + linea_limite, use_container_width=True)
            else:
                # Mensaje de ayuda si no se ha seleccionado nada en la grafica principal
                st.info("💡 Haz clic en un punto de la primera gráfica para desglosar los días aquí.")


    st.markdown("---") # Una línea sutil de separación visual
    '''
    col_ridge,col_historical = st.columns(2)
    with col_ridge:
        co.render_ridge_plot(df_total,pollutant_sel)
    with col_historical:
        co.render_historical_trends_chart_2(df_total,pollutant_sel)
    '''