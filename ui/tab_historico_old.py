# ui/tab_historico.py
import streamlit as st
import plotly.express as px
import core.model_configs as mc
import core.data_manager as dm
from datetime import datetime, timedelta
import altair as alt
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


import folium
from folium.plugins import HeatMapWithTime
from streamlit_folium import st_folium
from streamlit_folium import folium_static

COORDENADAS_ESTACIONES = {
    4: [40.4238, -3.7122], 8: [40.4215, -3.6823], 11: [40.4514, -3.6773],
    16: [40.4400, -3.6397], 17: [40.3471, -3.7133], 18: [40.3947, -3.7318],
    24: [40.4192, -3.7473], 27: [40.4769, -3.5800], 35: [40.4197, -3.7031],
    36: [40.4079, -3.6453], 38: [40.4455, -3.7071], 39: [40.4782, -3.7115],
    40: [40.3881, -3.6517], 47: [40.3981, -3.6868], 48: [40.4398, -3.6903],
    49: [40.4144, -3.6825], 50: [40.4656, -3.6887], 54: [40.3730, -3.6122],
    55: [40.4620, -3.5805], 56: [40.3850, -3.7186], 57: [40.4940, -3.6605],
    58: [40.5246, -3.7738], 59: [40.4652, -3.6172], 60: [40.5005, -3.6897]
}

# 1. Diccionario de estaciones
mapa_estaciones = {
    4: 'Plaza de España', 8: 'Escuelas Aguirre', 16: 'Arturo Soria',
    18: 'Farolillo', 24: 'Casa de Campo', 35: 'Plaza del Carmen',
    36: 'Moratalaz', 38: 'Cuatro Caminos', 39: 'Barrio del Pilar',
    54: 'Ensanche de Vallecas', 56: 'Plaza Elíptica', 58: 'El Pardo', 
    59: 'Juan Carlos I'
}


import altair as alt
import streamlit as st

def render_top_pollutant_bars(df, contaminante):
    if df.empty:
        st.warning("No hay datos para mostrar el Top 5.")
        return

    # Normalizamos el nombre a minúsculas como en el DataFrame
    col_pure = contaminante.lower()
    
    if col_pure not in df.columns:
        st.error(f"La columna '{col_pure}' no existe.")
        return

    # 1. Preparar el Top 5
    df_top = df.nlargest(5, col_pure).copy()
    df_top['fecha_display'] = df_top['timestamp'].dt.strftime('%d/%m %H:%M')

    st.subheader(f"Top 5 Máximos de {contaminante.upper()}")

    # 2. Crear la selección de Altair
    # Usamos 'selection_point' para capturar el clic en la barra
    selection = alt.selection_point(fields=['fecha_display'], name="Selector")

    # 3. Gráfico de Barras
    bars = alt.Chart(df_top).mark_bar(cornerRadiusEnd=4, cursor='pointer').encode(
        x=alt.X(f'{col_pure}:Q', title=f"Concentración ({contaminante.upper()})"),
        y=alt.Y('fecha_display:N', title="Fecha y Hora", sort='-x'),
        color=alt.condition(selection, alt.value('#ff4b4b'), alt.value('steelblue')),
        tooltip=[
            alt.Tooltip('timestamp:T', title='Fecha'),
            alt.Tooltip(f'{col_pure}:Q', title='Valor', format='.2f'),
            alt.Tooltip('intensidad:Q', title='Tráfico'),
            alt.Tooltip('temperatura:Q', title='Temp (ºC)'),
            alt.Tooltip('humedad:Q', title='Hum (%)'),
            alt.Tooltip('radiacion_solar:Q', title='Radiación solar (W/m²)'),
            alt.Tooltip('viento_velocidad:Q', title='Velocidad del viento (m/s)')
        ]
    ).add_params(
        selection
    ).properties(
        width='container',
        height=300
    )

    # Renderizar gráfico
    # Usamos on_select='rerun' para que Streamlit detecte el clic y podamos usarlo fuera del gráfico
    event = st.altair_chart(bars, use_container_width=True, on_select="rerun")

    # 4. Mostrar detalles del registro seleccionado[cite: 1]
    # Si hay una selección en el gráfico, filtramos y mostramos los datos
    if event and "Selector" in event["selection"] and event["selection"]["Selector"]:
        seleccionado = event["selection"]["Selector"][0]["fecha_display"]
        fila_detallada = df_top[df_top['fecha_display'] == seleccionado].iloc[0]

        st.markdown(f"### 📊 Detalles para el periodo: `{seleccionado} {contaminante}`")
        
        # Mostramos los datos en columnas para que sea visual[cite: 1]
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Tráfico (Intensidad)", f"{fila_detallada.get('intensidad', 0):.1f}")
        with c2:
            st.metric("Temperatura", f"{fila_detallada.get('temperatura', 0):.1f} °C")
        with c3:
            st.metric("Humedad", f"{fila_detallada.get('humedad', 0):.0f} %")
        with c4:
            st.metric("Radiación Solar", f"{fila_detallada.get('radiacion_solar', 0):.0f} W/m²")
        with c5:
            st.metric("Velocidad Viento", f"{fila_detallada.get('viento_velocidad', 0):.0f} m/s")
    else:
        st.info("👆 Haz clic en una barra roja para ver los parámetros detallados en este panel.")

@st.cache_data
def prepare_daily_averages(df, año, contaminante):
    """
    Reduce las 110.000 filas a unas pocas cientos (una por día/estación).
    Esto hace que el slider sea instantáneo.
    """
    col_cont = contaminante.lower()
    # Filtrar año y quitar nulos una sola vez
    df_year = df[df['timestamp'].dt.year == int(año)].copy()
    df_year = df_year.dropna(subset=[col_cont])
    
    # Calcular media diaria
    df_daily = df_year.groupby([df_year['timestamp'].dt.date, 'estacion_id'])[col_cont].mean().reset_index()
    return df_daily

def render_exceedance_bar_chart(df_anual, año_seleccionado, contaminante):
    st.markdown(f"### 📊 Análisis de Sensibilidad: {contaminante.upper()}")

    # 1. Obtener datos pre-procesados (esto será instantáneo tras la primera carga)
    df_daily = prepare_daily_averages(df_anual, año_seleccionado, contaminante)

    # 2. Slider (Ahora reaccionará mucho más rápido)
    config = {'no2': 40, 'o3': 120, 'pm10': 50, 'pm2_5': 25}
    default_val = config.get(contaminante.lower(), 40)
    
    umbral = st.slider(f"Límite {contaminante.upper()} (µg/m³)", 0, 150, default_val, 5)

    # 3. El filtrado ahora es sobre df_daily (muy pocas filas), casi 0 latencia
    df_exceed = df_daily[df_daily[contaminante.lower()] > umbral].copy()

    if not df_exceed.empty:
        # Mapeo de nombres
        df_exceed['estacion_id'] = df_exceed['estacion_id'].astype(int)
        df_exceed['Nombre Estación'] = df_exceed['estacion_id'].apply(
            lambda x: mapa_estaciones.get(x, f"Estación {x}")
        )
        
        df_counts = df_exceed.groupby('Nombre Estación').size().reset_index(name='Dias')
        df_counts = df_counts.sort_values('Dias', ascending=False)

        # Gráfico Altair
        chart = alt.Chart(df_counts).mark_bar(cornerRadius=10, height=20).encode(
            y=alt.Y('Nombre Estación:N', sort='-x', title=None),
            x=alt.X('Dias:Q', title='Días de superación'),
            color=alt.Color('Dias:Q', scale=alt.Scale(scheme='reds'), legend=None),
            tooltip=['Nombre Estación', 'Dias']
        ).properties(width='container', height=alt.Step(40))

        st.altair_chart(chart, use_container_width=True)
    else:
        st.success(f"✅ Ninguna estación supera los {umbral} µg/m³.")

# Coordenadas de las estaciones de Madrid
COORDENADAS_ESTACIONES = {
    4: [40.4238, -3.7122], 8: [40.4215, -3.6823], 11: [40.4514, -3.6773],
    16: [40.4400, -3.6397], 17: [40.3471, -3.7133], 18: [40.3947, -3.7318],
    24: [40.4192, -3.7473], 27: [40.4769, -3.5800], 35: [40.4197, -3.7031],
    36: [40.4079, -3.6453], 38: [40.4455, -3.7071], 39: [40.4782, -3.7115],
    40: [40.3881, -3.6517], 47: [40.3981, -3.6868], 48: [40.4398, -3.6903],
    49: [40.4144, -3.6825], 50: [40.4656, -3.6887], 54: [40.3730, -3.6122],
    55: [40.4620, -3.5805], 56: [40.3850, -3.7186], 57: [40.4940, -3.6605],
    58: [40.5246, -3.7738], 59: [40.4652, -3.6172], 60: [40.5005, -3.6897]
}

def render_pollution_heatmap(df, contaminante):
    """
    Mapa de calor temporal con fondo claro (Positron) y gradiente optimizado.
    """
    st.subheader(f"🌍 Evolución Geográfica: {contaminante.upper()}")
    
    col_cont = contaminante.lower()
    
    # 1. Limpieza: eliminamos nulos y valores negativos
    df_map = df.dropna(subset=[col_cont]).copy()
    df_map = df_map[df_map[col_cont] >= 0]
    
    if df_map.empty:
        st.warning(f"No hay datos para {contaminante}")
        return

    # 2. Eje temporal
    df_map['Mes_Año'] = df_map['timestamp'].dt.to_period('M').astype(str)
    tiempos = sorted(df_map['Mes_Año'].unique())
    
    # 3. Normalización
    max_val = float(df_map[col_cont].max())
    
    data_por_tiempo = []
    for t in tiempos:
        subset = df_map[df_map['Mes_Año'] == t]
        puntos_mes = []
        
        for _, row in subset.iterrows():
            est_id = int(row['estacion_id'])
            if est_id in COORDENADAS_ESTACIONES:
                lat, lon = COORDENADAS_ESTACIONES[est_id]
                val = float(row[col_cont])
                peso = round(val / max_val, 3) if max_val > 0 else 0
                puntos_mes.append([lat, lon, peso])
        
        if puntos_mes:
            data_por_tiempo.append(puntos_mes)

    # 4. Mapa base CLARO (CartoDB Positron)
    m = folium.Map(
        location=[40.4168, -3.7038], 
        zoom_start=12, 
        tiles="CartoDB positron"
    )

    # 5. Plugin HeatMap con gradiente adaptado a fondo claro
    HeatMapWithTime(
        data=data_por_tiempo,
        index=tiempos,
        radius=25,
        min_opacity=0.1,
        max_opacity=0.7,      # Un poco menos de opacidad para que se lea la calle debajo
        auto_play=False,
        display_index=True,
        gradient={
            0.2: '#00ccff', # Cian (limpio)
            0.4: '#00ff00', # Verde
            0.6: '#ffff00', # Amarillo
            0.8: '#ff6600', # Naranja
            1.0: '#ff0000'  # Rojo (máximo)
        }
    ).add_to(m)

    # 6. Mostrar en Streamlit
    folium_static(m)

def render_historical_trends_chart(df, contaminante):
    st.subheader(f"📈 Tendencia Histórica: {contaminante.upper()}")

    if df.empty:
        st.warning("No hay datos históricos.")
        return

    col_cont = contaminante.lower()
    df_plot = df.copy()
    
    # --- CAMBIO A NOMBRES REALES ---
    # Convertimos el ID a entero por si viene como string y mapeamos
    df_plot['estacion_id'] = df_plot['estacion_id'].astype(int)
    df_plot['Nombre Estación'] = df_plot['estacion_id'].map(mapa_estaciones).fillna(df_plot['estacion_id'].astype(str))
    
    # Año como string para estabilidad
    df_plot['Año'] = df_plot['timestamp'].dt.year.astype(str)

    # Agrupamos por Nombre de Estación en lugar de ID
    df_trend = df_plot.groupby(['Año', 'Nombre Estación'])[col_cont].mean().reset_index()

    # Filtro de seguridad para estaciones con datos
    estaciones_con_datos = df_trend.groupby('Nombre Estación')[col_cont].count()
    activas = estaciones_con_datos[estaciones_con_datos >= 2].index.tolist()
    df_final = df_trend[df_trend['Nombre Estación'].isin(activas)]

    if df_final.empty:
        st.info("No hay suficientes años de datos para mostrar una tendencia.")
        return

    # Visualización mejorada
    chart = alt.Chart(df_final).mark_line(
        point=alt.OverlayMarkDef(filled=True, size=40, color='white'),
        strokeWidth=3,
        interpolate='monotone'
    ).encode(
        x=alt.X('Año:N', title='Año'),
        y=alt.Y(f'{col_cont}:Q', 
                title=None, 
                scale=alt.Scale(zero=False),
                axis=alt.Axis(gridOpacity=0.1)),
        # Ahora usamos el nombre para el color y el faceteado
        color=alt.Color('Nombre Estación:N', scale=alt.Scale(scheme='tableau20'), legend=None),
        row=alt.Row('Nombre Estación:N', 
                    title=None, 
                    header=alt.Header(
                        labelColor='white', 
                        labelAngle=0, 
                        labelAlign='left',
                        labelFontSize=12,
                        labelFontWeight='bold'
                    )),
        tooltip=['Año', 'Nombre Estación', alt.Tooltip(f'{col_cont}:Q', format='.2f')]
    ).properties(
        width=650,
        height=100
    ).configure_view(
        stroke=None
    ).configure_axis(
        labelColor='white',
        titleColor='white'
    )

    st.altair_chart(chart, use_container_width=True)

def render_bubble_chart(df, contaminante):
    st.subheader("🫧 Análisis de Correlación Multidimensional")
    st.write("Relación entre Tráfico, Contaminación y Meteorología.")

    col_cont = contaminante.lower()
    df['hora'] = df['timestamp'].dt.hour
    # Creamos el gráfico de burbujas
    fig = px.scatter(
        df,
        x='intensidad',
        y=col_cont,
        size='temperatura', # El tamaño varía según la temperatura
        #color='viento_velocidad', # El color varía según el viento
        color='hora',
        color_continuous_scale='Twilight', # Escala circular (0 y 23h son parecidos)
        hover_name='timestamp',
        trendline="ols",
        trendline_color_override="red",
        labels={
            'intensidad': 'Tráfico (Veh/h)',
            col_cont: f'{contaminante.upper()} (µg/m³)',
            'temperatura': 'Temp',
            'viento_velocidad': 'Viento (m/s)'
        },

        #color_continuous_scale='Viridis', # Escala de colores profesional
    )

    # Ajustes estéticos para el fondo negro
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.1)", zeroline=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)", zeroline=False),
        coloraxis_colorbar=dict(title="Viento", tickfont=dict(color="white")),
        margin=dict(l=0, r=0, t=30, b=0),
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)



def render_gapminder_madrid(df):
    st.subheader("🎬 Dinámica Temporal: Tráfico vs Contaminación")
    st.markdown("""
    Esta gráfica animada muestra la evolución horaria. 
    **Eje X:** Tráfico | **Eje Y:** NO2 | **Tamaño:** PM10 | **Color:** Estación
    """)

    if df.empty:
        st.warning("No hay datos suficientes para la animación.")
        return

    # 1. Preparar el selector de tiempo (Slider de Altair)
    # Obtenemos los timestamps únicos y formateados para que se vean bien
    tiempos = sorted(df['timestamp'].unique())
    time_options = [i for i in range(len(tiempos))]
    
    # Mapeo de índices a etiquetas legibles (ej: "2025-04-15 08:00")
    labels = [pd.to_datetime(t).strftime('%d/%m %H:%M') for t in tiempos]
    
    slider = alt.binding_range(min=0, max=len(tiempos)-1, step=1, name='Progreso Temporal: ')
    select_time = alt.selection_point(
        name="Slider", 
        fields=['time_index'],
        bind=slider, 
        value={'time_index': 0}
    )

    # Añadimos el índice temporal al DataFrame para que el slider funcione
    time_map = {t: i for i, t in enumerate(tiempos)}
    df['time_index'] = df['timestamp'].map(time_map)

    # 2. Configuración de la gráfica de burbujas
    bubbles = alt.Chart(df).mark_point(filled=True, opacity=0.7, stroke='white', strokeWidth=0.5).encode(
        x=alt.X('intensidad:Q', 
                title='Intensidad de Tráfico (Vehículos/h)',
                scale=alt.Scale(domain=[0, df['intensidad'].max() * 1.1])),
        
        y=alt.Y('no2:Q', 
                title='Concentración NO2 (µg/m³)',
                scale=alt.Scale(domain=[0, df['no2'].max() * 1.1])),
        
        color=alt.Color('estacion_id:N', 
                       legend=alt.Legend(title="Estación"),
                       scale=alt.Scale(scheme='tableau20')),
        
        size=alt.Size('pm10:Q', 
                     title='Partículas PM10',
                     scale=alt.Scale(range=[100, 2000])),
        
        tooltip=[
            alt.Tooltip('timestamp:T', title='Fecha/Hora'),
            alt.Tooltip('estacion_id:N', title='Estación'),
            alt.Tooltip('intensidad:Q', title='Tráfico'),
            alt.Tooltip('no2:Q', title='NO2'),
            alt.Tooltip('temperatura:Q', title='Temp (°C)')
        ]
    ).add_params(
        select_time
    ).transform_filter(
        select_time
    ).properties(
        width='container',
        height=500
    )

    # 3. Texto de fondo con la fecha/hora actual
    # Esto crea el efecto "reloj" gigante detrás de las burbujas
    label_tiempo = alt.Chart(df).mark_text(
        align='right', baseline='bottom', fontSize=60, opacity=0.05, x=750, y=480
    ).encode(
        text=alt.Text('timestamp:T', format='%H:%M')
    ).transform_filter(
        select_time
    )

    # 4. Mostrar en Streamlit
    chart_final = (label_tiempo + bubbles).configure_view(stroke=None)
    st.altair_chart(chart_final, use_container_width=True)




def render_radar_chart(df, contaminante):
    st.subheader("🕸️ Perfil Comparativo: Picos vs Aire Limpio")
    
    col_cont = contaminante.lower()
    features = {
        col_cont: contaminante.upper(),
        'intensidad': 'Tráfico',
        'temperatura': 'Temp',
        'viento_velocidad': 'Viento',
        'humedad': 'Humedad',
        'radiacion_solar': 'Radiacion'
    }

    # Extraemos medias
    top_5 = df.nlargest(5, col_cont)
    bottom_5 = df.nsmallest(5, col_cont)

    fig = go.Figure()

    for estado, grupo, color in [('Máxima Contaminación', top_5, '#ff4b4b'), 
                                 ('Mínima Contaminación', bottom_5, '#00ffcc')]:
        valores = []
        nombres = []
        
        for col_db, nombre in features.items():
            v_min = df[col_db].min()
            v_max = df[col_db].max()
            val = grupo[col_db].mean()
            norm = (val - v_min) / (v_max - v_min) if (v_max - v_min) != 0 else 0
            valores.append(norm)
            nombres.append(nombre)

        # Cerramos el círculo del radar repitiendo el primer valor
        valores.append(valores[0])
        nombres.append(nombres[0])

        fig.add_trace(go.Scatterpolar(
            r=valores,
            theta=nombres,
            fill='toself',
            name=estado,
            line=dict(color=color)
        ))

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 1], gridcolor="gray", showticklabels=False),
            angularaxis=dict(gridcolor="gray", linecolor="white", tickfont=dict(color="white"))
        ),
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        margin=dict(l=80, r=80, t=20, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

def render_content():
    st.header("Análisis de Datos Históricos")

    col1, col2 = st.columns(2)

    with col1:
        # Selector de contaminante
        pollutant_sel = st.selectbox(
            "Selecciona el Contaminante", 
            mc.CONTAMINANTES_DISPONIBLES
        )

    # Filtrar códigos de estaciones que miden ese contaminante
    codigos_validos = [
        cod for cod, info in mc.ESTACIONES_MADRID.items() 
        if pollutant_sel in info["contaminantes"]
    ]

    with col2:
        # Selector de estación por CÓDIGO
        # format_func permite mostrar "Nombre" aunque el valor sea el "Código"
        codigo_sel = st.selectbox(
            "Selecciona la Estación",
            options=codigos_validos,
            format_func=lambda x: mc.ESTACIONES_MADRID[x]["nombre"],
            help="Solo se muestran estaciones que miden el gas seleccionado."
        )

    # --- SELECTORES DE FECHA ---
    st.subheader("Rango de fechas")
    col3, col4 = st.columns(2)
    
    with col3:
        # Por defecto, hace una semana atrás
        fecha_inicio = st.date_input(
            "Fecha inicio", 
            value=datetime.now() - timedelta(days=7),
            max_value=datetime.now()
        )
    
    with col4:
        fecha_fin = st.date_input(
            "Fecha fin", 
            value=datetime.now(),
            max_value=datetime.now()
        )

    # Validación básica de fechas
    if fecha_inicio > fecha_fin:
        st.error("Error: La fecha de inicio debe ser anterior a la fecha de fin.")
        return

    #st.info(f"Consultando datos para: {mc.ESTACIONES_MADRID[codigo_sel]['nombre']} (Código: {codigo_sel})")
    
    # Aquí iría tu llamada a la base de datos o API usando 'codigo_sel'
    # ejemplo: df = data_manager.get_data(estacion_id=codigo_sel, gas=pollutant_sel)
    
    # Diccionario de variables disponibles (puedes añadir más aquí)
    opciones_meteo = {
        "Viento (km/h)": "viento_velocidad",
        "Temperatura (°C)": "temperatura",
        "Humedad (%)": "humedad",
        "Presión (hPa)": "presion",
        "Radiación Solar": "radiacion_solar",
        "Intensidad Trafico (veh/h)": "intensidad"
    }

    #st.subheader("Configuración del panel")
    seleccionados = st.multiselect(
        "Selecciona qué parámetros meteorológicos mostrar:",
        options=list(opciones_meteo.keys()),
        default=["Viento (km/h)", "Temperatura (°C)"] # Valores por defecto
    )
    
    
    # 2. Carga de datos desde Mongo
    with st.spinner("Consultando datos..."):
        #df = dm.get_historical_data(codigo_sel, pollutant_sel,fecha_inicio,fecha_fin)
        df = dm.get_combined_data(codigo_sel, pollutant_sel, fecha_inicio, fecha_fin)
    # 3. Visualización
    
    # Llamada a la función que combina todo
    #df = dm.get_combined_data(codigo_sel, pollutant_sel, fecha_inicio, fecha_fin)

    st.info(f"{pollutant_sel} en {mapa_estaciones[codigo_sel]} entre {fecha_inicio} y {fecha_fin}")
    
    if not df.empty:
        # 1. Información técnica del DataFrame (columnas y tipos)
        '''
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Columnas detectadas:**")
            st.write(df.columns.tolist())
        
        with col2:
            st.write("**Dimensiones:**")
            st.write(f"{df.shape[0]} filas x {df.shape[1]} columnas")
        '''
        # 2. Vista interactiva del DataFrame
        #st.write("**Previsualización (primeras 50 filas):**")
        #st.dataframe(df.head(50))

        # 3. Descarga (útil para revisar en Excel si algo falla)
        '''
        st.download_button(
            "Descargar CSV para auditoría",
            df.to_csv(index=False).encode('utf-8'),
            "debug_datos.csv",
            "text/csv"
        )
        '''
        # 1. Definimos umbrales legales (Ejemplo NO2 según normativa europea/Madrid)
        UMBRALES = {"no2": 40, "pm10": 50, "pm2_5": 25, "so2": 125}

        if not df.empty:
            # Parámetros de interacción
            nearest = alt.selection_point(nearest=True, on='mouseover', fields=['timestamp'], empty=False)
            brush = alt.selection_interval(encodings=['x'])

            def create_chart(y_field, title, color, is_last=False, add_threshold=False):
                # 0. Capa de fondo para Fines de Semana
                # Detectamos Sábado (6) y Domingo (0) usando la función day() de Altair
                weekend_bg = alt.Chart(df).mark_rect(
                    color='rgba(250, 40, 70, 0.5)', # Gris muy suave
                    opacity=0.3
                ).encode(
                    x='timestamp:T',
                    x2='offset_timestamp:T', # Necesita un punto final para dibujar el bloque
                ).transform_calculate(
                    # Creamos un bloque de 1 hora (3600000 ms) para cada registro de finde
                    offset_timestamp="datum.timestamp + 3600000"
                ).transform_filter(
                    "(day(datum.timestamp) == 0) || (day(datum.timestamp) == 6)"
                )
                # 1. Base principal
                base = alt.Chart(df).encode(
                    x=alt.X('timestamp:T', axis=alt.Axis(title='Hora' if is_last else None, labels=is_last, gridOpacity=0.1)),
                    y=alt.Y(f'{y_field}:Q', title=title, scale=alt.Scale(zero=False))
                ).properties(width='container', height=180)

                # 2. El Área
                area = base.mark_area(
                    line={'color': color, 'strokeWidth': 2},
                    color=alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color=color, offset=0),
                            alt.GradientStop(color='transparent', offset=1)],
                        x1=1, x2=1, y1=1, y2=0
                    )
                ).add_params(brush)

                # 3. Interacción (Regla y punto)
                selectors = alt.Chart(df).mark_point().encode(x='timestamp:T', opacity=alt.value(0)).add_params(nearest)
                points = base.mark_point(color=color, fill='white').encode(opacity=alt.condition(nearest, alt.value(1), alt.value(0)))
                rule = alt.Chart(df).mark_rule(color='white', strokeDash=[4,4]).encode(x='timestamp:T').transform_filter(nearest)
                
                text = base.mark_text(align='left', dx=8, dy=-8, color='white', fontWeight='bold').encode(
                    text=alt.condition(nearest, f'{y_field}:Q', alt.value(' '))
                )

                layers = [weekend_bg, area, selectors, points, rule, text]

                # --- EL UMBRAL (CORREGIDO) ---
                if add_threshold and y_field in UMBRALES:
                    # Creamos una línea que recorre todo el eje X en el valor del umbral
                    thresh_line = alt.Chart(df).mark_rule(
                        color='#ff4b4b', 
                        strokeDash=[8,4], 
                        strokeWidth=2
                    ).encode(
                        y=alt.datum(UMBRALES[y_field])
                    )
                    layers.append(thresh_line)

                # Unimos y aplicamos el filtro de zoom (brush) al final
                return alt.layer(*layers).transform_filter(brush)
            
            
            # --- MONTAJE DINÁMICO ---
            charts = []
            
            # Fila 1: Contaminante (con umbral)
            cont_code = pollutant_sel.lower()
            charts.append(create_chart(cont_code, f"{pollutant_sel} (µg/m³)", "#00d1ff", is_last=False, add_threshold=True))

            # Filas extra: Meteorología
            meteo_colors = {"Viento (km/h)": "#ffeb3b", "Temperatura (°C)": "#ff4b4b", "Humedad (%)": "#00e676"}
            
            for i, nombre in enumerate(seleccionados):
                es_ultimo = (i == len(seleccionados) - 1)
                color = meteo_colors.get(nombre, "#ffffff")
                charts.append(create_chart(opciones_meteo[nombre], nombre, color, is_last=es_ultimo))

            # Renderizado final
            combined = alt.vconcat(*charts).configure_view(stroke=None).resolve_scale(x='shared')
            st.altair_chart(combined, use_container_width=True)
    
        st.divider()
        #st.write(df.columns.tolist())
        # Verificación de datos antes del radar
        #st.write("Conteo de datos no nulos:")
        #st.write(df[['temperatura', 'viento_velocidad', 'intensidad']].count())
        #radar_df = dm.get_radar_data(df, pollutant_sel.lower())
        #st.dataframe(radar_df.head(10))
        #render_radar_chart(df,pollutant_sel)
        st.divider()
        #render_bubble_chart(df, pollutant_sel)
    
        colRadar, colBuble = st.columns(2)
        with colRadar:
            render_radar_chart(df,pollutant_sel)
        with colBuble:
            render_bubble_chart(df,pollutant_sel)

        st.divider()
        #st.dataframe(df.head(10))
        render_top_pollutant_bars(df, pollutant_sel)

    else:
        st.warning("No hay datos suficientes para generar las gráficas vinculadas.")

    with st.spinner("Consultando MongoDB..."):
            #df = dm.get_historical_data(codigo_sel, pollutant_sel,fecha_inicio,fecha_fin)
            df_all = dm.get_all_contaminants_monthly(pollutant_sel)

    # 3. Visualización
        
        # Llamada a la función que combina todo
        #df = dm.get_combined_data(codigo_sel, pollutant_sel, fecha_inicio, fecha_fin)






        