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

# 1. Diccionario de estaciones
mapa_estaciones = {
    4: 'Plaza de España', 8: 'Escuelas Aguirre', 16: 'Arturo Soria',
    18: 'Farolillo', 24: 'Casa de Campo', 35: 'Plaza del Carmen',
    36: 'Moratalaz', 38: 'Cuatro Caminos', 39: 'Barrio del Pilar',
    54: 'Ensanche de Vallecas', 56: 'Plaza Elíptica', 58: 'El Pardo', 
    59: 'Juan Carlos I'
}



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

@st.cache_data
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


def render_historical_trends_chart(df, contaminante):
    st.subheader(f"📈 Tendencia Histórica: {contaminante.upper()}")

    if df.empty:
        st.warning("No hay datos históricos.")
        return

    col_cont = contaminante.lower()
    
    # 1. IDENTIFICAR COLUMNAS DUMMIES
    # Buscamos todas las columnas que empiecen por 'estacion_id_'
    cols_dummies = [c for c in df.columns if c.startswith('estacion_id_')]
    
    if not cols_dummies:
        st.error("No se encontraron columnas de estaciones (dummies) en los datos.")
        return

    # 2. REVERTIR DUMMIES (MELT)
    # Convertimos las columnas dummy en una sola fila por observacion
    # Mantenemos 'timestamp' y el valor del contaminante
    df_plot = df.melt(
        id_vars=['timestamp', col_cont], 
        value_vars=cols_dummies,
        var_name='temp_estacion_col',
        value_name='is_active'
    )

    # Filtrar solo donde el dummy es 1 (la estacion activa para ese registro)
    df_plot = df_plot[df_plot['is_active'] == 1].copy()

    # 3. EXTRAER ID Y MAPEAR NOMBRES REALES
    # Extraemos el numero final del nombre de la columna (ej: 'estacion_id_4' -> 4)
    df_plot['estacion_id'] = df_plot['temp_estacion_col'].str.replace('estacion_id_', '').astype(int)
    
    # Mapeamos usando tu diccionario mapa_estaciones
    df_plot['Nombre Estación'] = df_plot['estacion_id'].map(mapa_estaciones).fillna(df_plot['estacion_id'].astype(str))
    
    # 4. CONTINUAR CON TU LÓGICA ORIGINAL
    df_plot['Año'] = df_plot['timestamp'].dt.year.astype(str)

    # Agrupamos por Nombre de Estación
    df_trend = df_plot.groupby(['Año', 'Nombre Estación'])[col_cont].mean().reset_index()

    # Filtro de seguridad para estaciones con datos (al menos 2 años)
    estaciones_con_datos = df_trend.groupby('Nombre Estación')[col_cont].count()
    activas = estaciones_con_datos[estaciones_con_datos >= 2].index.tolist()
    df_final = df_trend[df_trend['Nombre Estación'].isin(activas)]

    if df_final.empty:
        st.info("No hay suficientes años de datos para mostrar una tendencia.")
        return

    # Visualización Altair (se mantiene igual, solo ajustamos el fondo negro)
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
        titleColor='white',
        gridColor='#333333'
    ).configure(
        background='transparent' # Para que use el fondo oscuro de Streamlit
    )

    st.altair_chart(chart, use_container_width=True)



def render_historical_trends_chart_2(df, contaminante):
    st.subheader(f"📊 Tendencia Histórica: {contaminante.upper()}")

    if df.empty:
        st.warning("No hay datos históricos.")
        return

    col_cont = contaminante.lower()
    
    # 1. IDENTIFICAR COLUMNAS DUMMIES
    cols_dummies = [c for c in df.columns if c.startswith('estacion_id_')]
    
    if not cols_dummies:
        st.error("No se encontraron columnas de estaciones en los datos.")
        return

    # 2. REVERTIR DUMMIES (MELT)
    df_plot = df.melt(
        id_vars=['timestamp', col_cont], 
        value_vars=cols_dummies,
        var_name='temp_estacion_col',
        value_name='is_active'
    )
    df_plot = df_plot[df_plot['is_active'] == 1].copy()

    # 3. EXTRAER ID Y MAPEAR NOMBRES
    df_plot['estacion_id'] = df_plot['temp_estacion_col'].str.replace('estacion_id_', '').astype(int)
    df_plot['Nombre Estación'] = df_plot['estacion_id'].map(mapa_estaciones).fillna(df_plot['estacion_id'].astype(str))
    
    # 4. PREPARAR DATOS POR AÑO
    df_plot['Año'] = df_plot['timestamp'].dt.year.astype(str)
    df_trend = df_plot.groupby(['Año', 'Nombre Estación'])[col_cont].mean().reset_index()

    # Filtro de seguridad (mínimo 1 año para barras, aunque 2 es mejor para comparar)
    estaciones_con_datos = df_trend.groupby('Nombre Estación')[col_cont].count()
    activas = estaciones_con_datos[estaciones_con_datos >= 1].index.tolist()
    df_final = df_trend[df_trend['Nombre Estación'].isin(activas)]

    # 5. CREACIÓN DEL GRÁFICO DE BARRAS
    chart = alt.Chart(df_final).mark_bar(
        cornerRadiusTopLeft=3,
        cornerRadiusTopRight=3,
        size=20 # Grosor de la barra
    ).encode(
        x=alt.X('Año:N', title='Año', axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f'{col_cont}:Q', 
                title=None, 
                scale=alt.Scale(zero=True), # En barras es mejor empezar desde 0
                axis=alt.Axis(gridOpacity=0.1)),
        color=alt.Color('Nombre Estación:N', 
                        scale=alt.Scale(scheme='tableau20'), 
                        legend=None),
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
        height=120 # Aumentamos un poco la altura para que las barras luzcan mejor
    ).configure_view(
        stroke=None
    ).configure_axis(
        labelColor='white',
        titleColor='white',
        gridColor='#333333'
    ).configure(
        background='transparent'
    )

    st.altair_chart(chart, use_container_width=True)


import plotly.graph_objects as go
import pandas as pd

import plotly.graph_objects as go
import pandas as pd

def render_historical_candlestick_trimestral(df, contaminante):
    st.subheader(f"🕯️ Variabilidad Trimestral: {contaminante.upper()}")

    col_cont = contaminante.lower()
    
    # 1. Recuperar estaciones desde dummies
    cols_dummies = [c for c in df.columns if c.startswith('estacion_id_')]
    if not cols_dummies:
        st.warning("No se detectaron columnas de estaciones.")
        return

    df_plot = df.melt(
        id_vars=['timestamp', col_cont], 
        value_vars=cols_dummies,
        var_name='temp_estacion_col',
        value_name='is_active'
    )
    
    # Solo filas activas y asegurar que el timestamp sea datetime
    df_plot = df_plot[df_plot['is_active'] == 1].copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp'])
    
    # Mapeo de nombres (Asegúrate de que 'mapa_estaciones' sea accesible)
    df_plot['Nombre Estación'] = df_plot['temp_estacion_col'].str.replace('estacion_id_', '').astype(int).map(mapa_estaciones)

    # 2. Agrupación Trimestral limpia
    # Agrupamos y eliminamos filas con NaN por si acaso
    df_stats = df_plot.groupby(['Nombre Estación', pd.Grouper(key='timestamp', freq='3ME')])[col_cont].agg(
        minimo='min',
        maximo='max',
        media='mean'
    ).reset_index().dropna()

    if df_stats.empty:
        st.info("Datos insuficientes para generar trimestres.")
        return

    fig = go.Figure()

    # 3. Construcción del gráfico
    for estacion in df_stats['Nombre Estación'].unique():
        df_est = df_stats[df_stats['Nombre Estación'] == estacion].sort_values('timestamp')
        
        fig.add_trace(go.Candlestick(
            x=df_est['timestamp'],
            open=df_est['media'],
            high=df_est['maximo'],
            low=df_est['minimo'],
            close=df_est['media'],
            name=estacion,
            hovertemplate=(
                "<b>Estación:</b> " + str(estacion) + "<br>" +
                "<b>Máximo:</b> %{high:.2f}<br>" +
                "<b>Media:</b> %{open:.2f}<br>" +
                "<b>Mínimo:</b> %{low:.2f}<extra></extra>"
            ),
            increasing_line_color='#ef5350',
            decreasing_line_color='#66bb6a'
        ))

    # 4. Forzar visibilidad en modo oscuro
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='black',
        plot_bgcolor='black',
        xaxis_title="Trimestres",
        yaxis_title="µg/m³",
        xaxis_rangeslider_visible=False,
        height=400,
        hovermode='x unified',
        # Esto asegura que si hay pocos datos, el gráfico no se encoja
        xaxis=dict(type='date', gridcolor='#333333'),
        yaxis=dict(gridcolor='#333333')
    )

    st.plotly_chart(fig, use_container_width=True)


@st.cache_data
def prepare_ridge_data(df, contaminante):
    # Todo el procesamiento pesado se queda aquí
    col_cont = contaminante.lower()
    df_plot = df.copy()
    
    meses_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    df_plot['mes_num'] = df_plot['timestamp'].dt.month
    df_plot['mes_nombre'] = df_plot['mes_num'].map(meses_es)
    
    # Devolvemos solo lo necesario para graficar
    return df_plot[['mes_num', 'mes_nombre', col_cont]].dropna()


def render_ridge_plot(df, contaminante):
    st.subheader(f"🏔️ Distribución Mensual: {contaminante.upper()}")

    # 1. Obtener datos procesados (desde cache)
    df_ready = prepare_ridge_data(df, contaminante)
    col_cont = contaminante.lower()
    
    if df_ready.empty:
        st.warning("No hay datos suficientes para generar el grafico de montaña.")
        return

    # 2. Obtener meses presentes y ordenarlos cronologicamente
    meses_ordenados = sorted(df_ready['mes_num'].unique())
    meses_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }

    fig = go.Figure()

    # 3. Construcción de las "montañas" (Violin traces)
    for num_mes in meses_ordenados:
        mes_txt = meses_es[num_mes]
        datos_mes = df_ready[df_ready['mes_num'] == num_mes][col_cont]
        
        fig.add_trace(go.Violin(
            x=datos_mes,
            line_color='white',
            # Alternancia de colores: Rojo suave y Naranja
            fillcolor='rgba(239, 83, 80, 0.6)' if num_mes % 2 == 0 else 'rgba(255, 152, 0, 0.6)',
            name=mes_txt,
            side='positive',
            width=3, # Factor de solapamiento
            points=False,
            meanline_visible=True,
            showlegend=False
        ))

    # 4. Ajustes de diseño y estetica Dark
    fig.update_traces(orientation='h', side='positive', width=3, points=False)
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='black',
        plot_bgcolor='black',
        height=700,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title=f"Concentración de {contaminante.upper()} (µg/m³)",
        violinmode='overlay'
    )

    # Invertir el eje Y para que el año empiece en Enero (arriba)
    fig.update_yaxes(
        autorange="reversed", 
        gridcolor='#333333',
        showgrid=False,
        zeroline=False
    )
    
    fig.update_xaxes(
        gridcolor='#333333',
        showgrid=True,
        zeroline=False
    )

    # Límite de la Media Anual (40 µg/m³)
    fig.add_vline(
        x=40, 
        line_dash="dash", 
        line_color="rgba(255, 255, 0, 0.5)", # Amarillo semi-transparente
        annotation_text="Límite Anual (40)", 
        annotation_position="top",
        annotation_font_color="yellow"
    )

    # Límite del Pico Horario (200 µg/m³)
    fig.add_vline(
        x=200, 
        line_dash="dot", 
        line_color="rgba(255, 0, 0, 0.5)", # Rojo semi-transparente
        annotation_text="Límite Horario (200)", 
        annotation_position="top",
        annotation_font_color="red"
    )

    # 5. Renderizar en Streamlit
    st.plotly_chart(fig, use_container_width=True)
