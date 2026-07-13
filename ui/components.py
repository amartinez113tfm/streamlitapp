import streamlit as st
import plotly.express as px
import core.model_configs as mc
import core.data_manager as dm
from datetime import datetime, timedelta
import altair as alt
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.figure_factory as ff

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

# 1. CAPA BASE: Definimos solo los ejes comunes X e Y
    base = alt.Chart(df_final).encode(
        x=alt.X('Año:N', title='Año', axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f'{col_cont}:Q', 
                title=None, 
                scale=alt.Scale(zero=True),
                axis=alt.Axis(grid=True, gridOpacity=0.4)), # Grid horizontal nitido
        color=alt.Color('Nombre Estación:N', 
                        scale=alt.Scale(scheme='tableau20'), 
                        legend=None),
        tooltip=['Año', 'Nombre Estación', alt.Tooltip(f'{col_cont}:Q', format='.2f')]
    )

    # 2. DEFINICIÓN DE COMPONENTES INDIVIDUALES
    linea = base.mark_line(strokeWidth=4)
    puntos = base.mark_point(filled=True, size=60)
    
    texto_valores = base.mark_text(
        align='center',
        baseline='bottom',
        dy=-10,
        fontSize=13,
        fontWeight='bold',
        color='white'
    ).encode(
        text=alt.Text(f'{col_cont}:Q', format='.1f')
    )

    # 3. COMBINACIÓN CORRECTA DE MÉTODOS:
    # Primero unimos las capas, segundo aplicamos propiedades a la celda, y al final facetamos
    chart = (linea + puntos + texto_valores).properties(
        width='container',
        height=100 # 🟢 Se define aqui el tamaño de cada mini-grafico individual
    ).facet(
        row=alt.Row('Nombre Estación:N', 
                    title=None, 
                    header=alt.Header(
                        labelColor='gray', 
                        labelAngle=0, 
                        labelAlign='left',
                        labelFontSize=15,
                        labelFontWeight='bold',
                        labelPadding=15
                    ))
    ).configure_view(
        stroke=None
    ).configure_axis(
        labelColor='white',
        titleColor='white',
        gridColor='#555555' # Color gris claro para destacar el grid horizontal
    ).configure(
        background='transparent'
    )

    st.altair_chart(chart, use_container_width=True)

    

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



def render_historical_overages_chart(df_filtrado, col_cont):
    """
    Genera y muestra una grafica de barras horizontales en Altair con las veces
    que se han superado los limites legales por estacion para el año activo.
    df_filtrado: DataFrame ya filtrado con 'Veces Superado' > 0, el año y contaminante elegidos.
    """
    if df_filtrado.empty:
        st.info(f"✨ Ninguna estacion registro superaciones de los limites para {col_cont} en este periodo.")
        return

    # 1. CAPA BASE: Definimos los ejes comunes X e Y (SIN meter el row todavia)
    # Colocamos el numero de veces en el eje X para que la barra crezca horizontalmente
    base = alt.Chart(df_filtrado).encode(
        x=alt.X('Veces Superado:Q', 
                title='Nº Veces Superado al Año',
                axis=alt.Axis(
                    grid=True, 
                    gridOpacity=0.4, 
                    tickMinStep=1, # Fuerza a que los pasos del grid sean enteros (1, 2, 3...)
                    labelColor='white',
                    titleColor='white'
                )),
        # Dejamos el eje Y sin titulos ni etiquetas porque el nombre se leera en el Header lateral
        y=alt.Y('Estación:N', title=None, axis=None),
        color=alt.Color('Estación:N', 
                        scale=alt.Scale(scheme='tableau20'), 
                        legend=None),
        tooltip=['Año', 'Estación', 'Contaminante', 'Límite Aplicado', 'Veces Superado']
    )

    # 2. DEFINICIÓN DE LA BARRA HORIZONTAL CON BORDES REDONDEADOS
    barras = base.mark_bar(
        cornerRadiusTopRight=3,
        cornerRadiusBottomRight=3,
        size=16 # Espesor elegante de la barra
    )

    # 3. CAPA DE TEXTO EN LOS EXTREMOS (Opcional pero muy visual)
    # Muestra el numero exacto al final de cada barra para que no haya que adivinar con el grid
    texto_valores = base.mark_text(
        align='left',
        baseline='middle',
        dx=5, # Desplazamiento de 5 pixeles a la derecha de la barra
        fontSize=11,
        fontWeight='bold',
        color='white'
    ).encode(
        text=alt.Text('Veces Superado:Q')
    )

    # 4. UNIÓN DE CAPAS, DIMENSIONES Y FACETADO (El orden que exige Altair)
    chart = (barras + texto_valores).properties(
        width=325, # Ancho idéntico al de tu grafica de lineas para que queden simetricas en las columnas
        height=60  # Altura de 60px por estacion, clavado a tu diseño actual
    ).facet(
        row=alt.Row('Estación:N', 
                    title=None, 
                    header=alt.Header(
                        labelColor='gray', 
                        labelAngle=0, 
                        labelAlign='left',
                        labelFontSize=12,
                        labelFontWeight='bold'
                    ))
    ).configure_view(
        stroke=None
    ).configure_axis(
        gridColor='#555555' # Mismo gris claro para el grid horizontal de fondo
    ).configure(
        background='transparent'
    )

    # 5. Renderizado final en Streamlit adaptándose al contenedor de la columna
    st.altair_chart(chart, use_container_width=True)


import altair as alt
import streamlit as st

def render_historical_overages_trends(df_filtrado, col_cont):
    """
    Genera y muestra una grafica de lineas facetada por estacion para el historico
    de superaciones de limites, variando el color por año y mostrando el valor de cada uno.
    df_filtrado: DataFrame con 'Veces Superado' > 0 (historico completo de años).
    """
    st.subheader(f"📊 Superación de límites legales {col_cont.upper()}: {df_filtrado['Límite Aplicado'].iloc[0]}")
    if df_filtrado.empty:
        st.info(f"✨ Ninguna estacion registro superaciones de los limites para {col_cont} en el historico.")
        return

    # 1. CAPA BASE: Definimos los ejes comunes X e Y (SIN meter el row todavia)
    # Forzamos a que el Año sea de tipo Ordinal (O) o Nominal (N) para los colores
    base = alt.Chart(df_filtrado).encode(
        x=alt.X('Año:O', title='Año', axis=alt.Axis(labelAngle=0, labelColor='black', titleColor='white')),
        y=alt.Y('Veces Superado:Q', 
                title=None, 
                scale=alt.Scale(zero=True),
                axis=alt.Axis(grid=True, gridOpacity=0.4, labelColor='white', titleColor='white')),
        tooltip=['Año', 'Estación', 'Contaminante', 'Límite Aplicado', 'Veces Superado']
    )

    # 2. CAPA DE LÍNEA: Conecta los años de forma continua
    # Usamos un color base fijo (gris claro) para unir el trazado de la tendencia temporal
    linea = base.mark_line(
        strokeWidth=2.5,
        color='#A0AEC0',
        opacity=0.6
    )

    # 3. CAPA DE PUNTOS: Cambia de color segun el año
    puntos = base.mark_point(
        filled=True, 
        size=45
    ).encode(
        color=alt.Color('Año:N', scale=alt.Scale(scheme='tableau10'), legend=None)
    )
    
    # 4. CAPA DE TEXTO: Muestra el valor numerico encima de cada año y cambia de color
    texto_valores = base.mark_text(
        align='center',
        baseline='bottom',
        dy=-8, # Desplazamiento hacia arriba del punto
        fontSize=10,
        fontWeight='bold'
    ).encode(
        text=alt.Text('Veces Superado:Q', format='d'), # Formato entero
        color=alt.Color('Año:N', scale=alt.Scale(scheme='tableau10'), legend=None)
    )

    # 5. UNIÓN DE CAPAS, DIMENSIONES Y FACETADO POR ESTACIÓN (Igual a tu captura)
    chart = (linea + puntos + texto_valores).properties(
        width=325, # Ancho identico para mantener la simetria en paralelo
        height=60  # Perfil bajo vertical (60px) por cada estacion
    ).facet(
        row=alt.Row('Estación:N', 
                    title=None, 
                    header=alt.Header(
                        labelColor='gray', 
                        labelAngle=0, 
                        labelAlign='left',
                        labelFontSize=12,
                        labelFontWeight='bold'
                    ))
    ).configure_view(
        stroke=None
    ).configure_axis(
        gridColor='#555555' # Mismo tono de rejilla horizontal
    ).configure(
        background='transparent'
    )

    # 6. Renderizado final en Streamlit
    st.altair_chart(chart, use_container_width=True)




def render_historical_overages_trends_2(df_filtrado, col_cont):
    """
    Genera la gráfica de líneas de superaciones habilitando la selección por clic.
    Devuelve una tupla: (objeto_chart, seleccion_altair)
    """
    if df_filtrado.empty:
        st.info(f"✨ Ninguna estación registró superaciones de los límites para {col_cont} en el histórico.")
        return None, None

    limite_legal_texto = df_filtrado['Límite Aplicado'].iloc[0]
    st.markdown(f"**📌 Criterio evaluado:** {limite_legal_texto}")

    # 🟢 1. CREAR EL PARAMETRO DE SELECCIÓN DE ALTAIR
    # Capturará el 'Año' y la 'Estación' cuando el usuario haga clic en un nodo
    seleccion = alt.selection_point(
        fields=['Año', 'Estación'], 
        on='click',
        name='selector_clic'
    )

    # 2. CAPA BASE
    base = alt.Chart(df_filtrado).encode(
        x=alt.X('Año:O', title='Año', axis=alt.Axis(labelAngle=0, labelColor='white', titleColor='white')),
        y=alt.Y('Veces Superado:Q', 
                title=None, 
                scale=alt.Scale(zero=True),
                axis=alt.Axis(grid=True, gridOpacity=0.4, labelColor='white', titleColor='white')),
        tooltip=['Año', 'Estación', 'Contaminante', 'Límite Aplicado', 'Veces Superado']
    )

    # 3. CAPA DE LÍNEA
    linea = base.mark_line(strokeWidth=2.5, color='#A0AEC0', opacity=0.6)

    # 4. CAPA DE PUNTOS (Vinculada a la selección y cambia opacidad si no está seleccionado)
    puntos = base.mark_point(
        filled=True, 
        size=70 # Un pelín más grande para facilitar el clic físico
    ).encode(
        color=alt.Color('Año:N', scale=alt.Scale(scheme='tableau10'), legend=None),
        opacity=alt.condition(seleccion, alt.value(1.0), alt.value(0.25)) # Efecto visual al clicar
    ).add_params(
        seleccion # 🟢 Acoplamos el escuchador de clics aquí
    )
    
    # 5. CAPA DE TEXTO
    texto_valores = base.mark_text(
        align='center', baseline='bottom', dy=-10, fontSize=10, fontWeight='bold'
    ).encode(
        text=alt.Text('Veces Superado:Q', format='d'),
        color=alt.Color('Año:N', scale=alt.Scale(scheme='tableau10'), legend=None),
        opacity=alt.condition(seleccion, alt.value(1.0), alt.value(0.3))
    )

    # 6. UNIÓN Y FACETADO
    chart = (linea + puntos + texto_valores).properties(
        width=325, height=60 
    ).facet(
        row=alt.Row('Estación:N', title=None, 
                    header=alt.Header(labelColor='gray', labelAlign='left', labelFontSize=12, labelFontWeight='bold'))
    ).configure_view(
        stroke=None
    ).configure_axis(
        gridColor='#555555'
    ).configure(
        background='transparent'
    )

    return chart, seleccion

# --- Dentro del archivo donde guardas tus funciones de graficos (ej. co.py o similar) ---

# --- Dentro de ui/components.py ---

def render_historical_overages_trends_3(df_superaciones, pollutant_sel):
    """
    Genera el grafico de barras horizontales usando las columnas reales 
    del dataframe: 'Veces Superado' y la columna de la estacion.
    """
    if df_superaciones is None or df_superaciones.empty:
        return None, None

    # Copiamos para no alterar el dataframe original por referencia
    df_chart = df_superaciones.copy()

    # 1. Normalizacion de nombres de columnas para asegurar compatibilidad
    # Si la columna viene como 'Veces Superado', la mapeamos internamente
    col_valores = 'Veces Superado' if 'Veces Superado' in df_chart.columns else df_chart.columns[-1]
    
    # Nos aseguramos de que existan las columnas 'Año' y 'Estación' con tilde para el selector de Streamlit
    if 'Año' not in df_chart.columns and 'Anio' in df_chart.columns:
        df_chart = df_chart.rename(columns={'Anio': 'Año'})
    elif 'Año' not in df_chart.columns:
        # Si no viene el año, asumimos que puede extraerse o venir en otra columna
        df_chart['Año'] = 2019 # Valor por defecto de respaldo si no existiera
        
    # Detectamos la columna que contiene los nombres de las estaciones (Barrio del Pilar, Plaza Eliptica, etc.)
    col_estacion = None
    for c in df_chart.columns:
        if c in ['Estación', 'Estacion', 'Nombre Estación', 'Nombre']:
            col_estacion = c
            break
    
    if col_estacion is None:
        # Si viene oculta o como texto suelto, buscamos la primera columna de texto
        col_estacion = df_chart.select_dtypes(include=['object']).columns[0]
        
    # Renombramos a 'Estación' para que el selector por clic de Streamlit no se rompa
    df_chart = df_chart.rename(columns={col_estacion: 'Estación'})

    # 2. Definimos el selector de seleccion por clic para las barras horizontales
    selector_clic = alt.selection_point(
        name="selector_clic",
        fields=["Año", "Estación"],
        on="click"
    )

    # 3. CAPA BASE: Vinculamos los ejes usando los nombres reales de las columnas
    base = alt.Chart(df_chart).encode(
        x=alt.X(f'{col_valores}:Q', 
                title='Nº de Superaciones',
                axis=alt.Axis(grid=True, labelFontSize=12, titleFontSize=13)),
        y=alt.Y('Año:O', 
                title=None,
                axis=alt.Axis(labelFontSize=12)),
        color=alt.condition(
            selector_clic,
            alt.Color('Estación:N', scale=alt.Scale(scheme='tableau20'), legend=None),
            alt.value('lightgray') # Cambia a gris al seleccionar otra barra
        ),
        tooltip=['Año', 'Estación', alt.Tooltip(f'{col_valores}:Q', title='Superaciones')]
    ).add_params(
        selector_clic
    )

    # 4. COMPONENTES: Barras con esquinas suavizadas + texto del valor a la derecha
    barras = base.mark_bar(cornerRadiusEnd=3, height=16)
    
    texto_valores = base.mark_text(
        align='left',
        baseline='middle',
        dx=6,
        fontSize=12,
        fontWeight='bold',
        color='white'
    ).encode(
        text=alt.Text(f'{col_valores}:Q', format='.0f')
    )

    # 5. COMBINACIÓN Y FACETADO POR ESTACIÓN
    chart_final = (barras + texto_valores).properties(
        width='container',
        height=75 # Altura perfecta para que cada barra respire por año
    ).facet(
        row=alt.Row('Estación:N', 
                    title=None, 
                    header=alt.Header(
                        labelColor='gray', 
                        labelAngle=0, 
                        labelAlign='left',
                        labelFontSize=14,
                        labelFontWeight='bold',
                        labelPadding=12
                    ))
).configure_view(
        stroke=None
    ).configure_axis(
        labelColor='white',
        titleColor='white',
        gridColor='#555555'
    ).configure(
        background='transparent'
    )

    return chart_final, selector_clic



def dibujar_matriz_plotly(cm, limite):
            # Definimos las etiquetas
            x = ['Bajo Limite', 'Supera Limite']
            y = ['Bajo Limite', 'Supera Limite']

            # Invertimos la matriz para que coincida con el orden visual (Realidad en Y, Prediccion en X)
            # Plotly a veces dibuja de abajo hacia arriba, asi que le damos formato
            z = cm

            # Crear el heatmap con anotaciones (figure factory es genial para esto)
            fig = ff.create_annotated_heatmap(
                z=z, 
                x=x, 
                y=y, 
                annotation_text=z.astype(str), 
                colorscale='Blues'
            )

            # Añadir titulos y ajustar margenes
            fig.update_layout(
                title=f'Matriz de Confusion (Limite: {limite} µg/m³)',
                xaxis_title='Prediccion',
                yaxis_title='Realidad',
                width=450,
                height=450,
                margin=dict(l=50, r=50, t=80, b=50)
            )

            return fig


#Este bloque va en la pestaña de predicciones
def graficos_24horas(df_final):
    # (No ponemos tildes en los comentarios de codigo)

    if df_final is not None and not df_final.empty:
        st.success("¡Datos cargados con exito!")
        
        # --- SECCIÓN 1: MÉTRICAS RESUMEN (MEDIAS DE 24 HORAS) ---
        st.subheader("📊 Resumen medio de las ultimas 24 horas comunes")
        
        # Creamos un sistema de columnas para mostrar los KPI de forma elegante
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Media de Ozono y NO2
            o3_medio = df_final["o3"].mean()
            st.metric(label="O₃ Medio", value=f"{o3_medio:.1f} µg/m³")
            no2_medio = df_final["no2"].mean()
            st.metric(label="NO₂ Medio", value=f"{no2_medio:.1f} µg/m³")
            
        with col2:
            pm10_medio = df_final["pm10"].mean()
            st.metric(label="Partículas 10mm Medio", value=f"{pm10_medio:.1f} µg/m³")
            pm2_5_medio = df_final["pm2_5"].mean()
            st.metric(label="Partículas 10mm Medio", value=f"{pm2_5_medio:.1f} µg/m³")
            
        with col3:
            # Media de Temperatura y Humedad (si existen en tus variables)
            temp_media = df_final["temperatura"].mean()
            st.metric(label="Temp. Media", value=f"{temp_media:.1f} °C")
            humedad_media = df_final["humedad"].mean()
            st.metric(label="Humedad Media", value=f"{humedad_media:.1f} %")
            
        with col4:
            # Media del tráfico (la columna que renombramos como 'intensidad')
            trafico_medio = df_final["intensidad"].mean()
            st.metric(label="Tráfico Medio", value=f"{trafico_medio:.0f} veh/h")

        st.markdown("---")

        # --- SECCIÓN 2: MINIGRÁFICAS (TENDENCIAS METEOROLÓGICAS Y TRÁFICO) ---
        st.subheader("📈 Evolución temporal del bloque de entrada")
        
        # Preparamos un dataframe con el timestamp de indice para que los graficos pinten la hora en el eje X
        df_lineas = df_final.set_index("timestamp")
        
        # Usamos pestañas (tabs) para organizar las graficas sin saturar la pantalla
        tab1, tab2, tab3 = st.tabs(["🌡️ Meteorología", "🚗 Tráfico", "🧪 Contaminantes"])
        
        with tab1:
            st.write("Evolución de la Temperatura y condiciones climáticas")
            # Grafico con la temperatura
            st.line_chart(df_lineas[["temperatura"]])
            
            # Si tienes viento o humedad, puedes añadir otro grafico pequeño aqui
            if "viento_velocidad" in df_lineas.columns:
                st.line_chart(df_lineas[["viento_velocidad"]])
                
        with tab2:
            st.write("Intensidad de tráfico en el entorno de la estación")
            st.line_chart(df_lineas[["intensidad"]])
            
        with tab3:
            st.write("Historial de los gases de entrada para la red GRU")
            # Pintamos O3 y NO2 juntos para ver como interactúan
            st.line_chart(df_lineas[["o3", "no2"]])

        st.markdown("---")
