import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import MousePosition
from folium.plugins import TimestampedGeoJson
from folium.plugins import HeatMap
import seaborn as sns
import matplotlib.pyplot as plt
import streamlit as st
from pathlib import Path
from util import corregir_acentos, remover_acentos
from functools import reduce
from data_generation import leer_contaminante_raster
from branca.colormap import linear
import branca.colormap as cm



# Configuración 
pd.set_option('display.float_format', '{:,.2f}'.format)

# Obtener ruta del proyecto
BASE_DIR = Path(__file__).resolve().parent
AQI_DATA_PATH = BASE_DIR / "data" / "valores_contaminantes_por_estaciones_cdmx.csv"

gdf_total = gpd.GeoDataFrame(pd.read_csv(AQI_DATA_PATH, encoding='latin-1'))

#Archivos raster
archivos = {
    "CO":  (BASE_DIR / "data" / "CO.nc",  "carbonmonoxide_total_column"),
    "NO2": (BASE_DIR / "data" / "NO2.nc", "nitrogendioxide_tropospheric_column"),
    "SO2": (BASE_DIR / "data" / "SO2.nc", "sulfurdioxide_total_vertical_column"),
    "O3":  (BASE_DIR / "data" / "O3.nc",  "ozone_total_vertical_column"),
    "AER": (BASE_DIR / "data" / "AER.nc","aerosol_mid_pressure")
}

gdfs = []


# Carga de Municipios CDMX

mx = gpd.read_file( BASE_DIR / "data" / "mun21gw" / "mun21gw.shp")
mx['NOM_ENT'] = mx['NOM_ENT'].apply(remover_acentos)
cdmx = mx[(mx['NOM_ENT'] == 'Ciudad de MAxico') | (mx['NOM_ENT'] == 'MAxico')]

#Obtención de promedios Anuales

promedios_anuales = (
    gdf_total
    .groupby(['ESTACION', 'TIPO_CONTAMINANTE', 'latitud', 'longitud'], as_index=False)['AQI']
    .mean()
)

aqi_anual_estaciones = (
    promedios_anuales.loc[promedios_anuales.groupby('ESTACION')['AQI'].idxmax()]
    .reset_index(drop=True)
)

aqi_cdmx = gpd.GeoDataFrame(
    aqi_anual_estaciones,
    geometry=gpd.points_from_xy(aqi_anual_estaciones['longitud'], aqi_anual_estaciones['latitud']),
    crs="EPSG:4326"
)

# Spatial join: asignar cada punto de estación al polígono donde se encuentra
df_con_municipios = gpd.sjoin(aqi_cdmx, cdmx, how="left", predicate="within")

df_con_municipios = df_con_municipios[['ESTACION','NOM_MUN','TIPO_CONTAMINANTE','AQI']]
df_con_municipios['NOM_MUN'] = df_con_municipios['NOM_MUN'].apply(corregir_acentos)

#Filtrado
lista_municipios = df_con_municipios['NOM_MUN'].unique().tolist()
lista_municipios.sort()
opciones_municipios = ['Todos'] + lista_municipios

# Crear el selectbox en la barra lateral
municipio_seleccionado = st.sidebar.selectbox(
    'Selecciona un municipio',
    opciones_municipios
)

# ----- Filtrar datos según la selección -----

# --------------------------------------------------------------------
# --------------------- NUEVO FILTRO POR CONTAMINANTE ----------------
# --------------------------------------------------------------------

lista_contaminantes = df_con_municipios["TIPO_CONTAMINANTE"].unique().tolist()
lista_contaminantes.sort()
opciones_contaminantes = ["Todos"] + lista_contaminantes

contaminante_seleccionado = st.sidebar.selectbox(
    "Selecciona un contaminante",
    opciones_contaminantes
)

# Aplicación conjunta de filtros municipio + contaminante
datos_filtrados = df_con_municipios.copy()

if municipio_seleccionado != "Todos":
    datos_filtrados = datos_filtrados[datos_filtrados["NOM_MUN"] == municipio_seleccionado]

if contaminante_seleccionado != "Todos":
    datos_filtrados = datos_filtrados[datos_filtrados["TIPO_CONTAMINANTE"] == contaminante_seleccionado]

# Renombrar final siempre al terminar filtros
datos_filtrados = datos_filtrados.rename(columns={
    'ESTACION': 'Estacion',
    'NOM_MUN': 'Municipio',
    'TIPO_CONTAMINANTE': 'Contaminante Prevalente',
    'AQI': 'Indice de Calidad del Aire'
})


# Mostrar la tabla
st.subheader('AQI (Air Quality Index) Promedio Anual por Municipio de la Ciudad México')
datos_filtrados = datos_filtrados.rename(columns={
    'ESTACION': 'Estacion',
    'NOM_MUN': 'Municipio',
    'TIPO_CONTAMINANTE': 'Contaminante Prevalente',
    'AQI': 'Indice de Calidad del Aire'
})
st.dataframe(datos_filtrados, hide_index=True)


#Gráfico de Barras para valores de AQI por contaminante

aqi_prom = gdf_total.groupby('TIPO_CONTAMINANTE')['AQI'].mean().reset_index()
fig = px.bar(
    aqi_prom,
    x='TIPO_CONTAMINANTE',
    y='AQI',
    title='Valores promedio de AQI obtenidos por contaminante',
    labels={
        'TIPO_CONTAMINANTE': 'Contaminante',
        'AQI': 'AQI Promedio'
    },
    width=1000,   # Ancho de la figura en píxeles
    height=600    # Alto de la figura en píxeles
)

# Actualizar el formato del eje y evitar notación científica
fig.update_yaxes(tickformat=",d")

# Atributos globales de la figura
fig.update_layout(
    xaxis_title=dict(
        font=dict(size=16)
    ),
    yaxis_title=dict(
        font=dict(size=16)
    )
)
# Despliegue del gráfico
st.subheader("Gráficos relacionados al Índice de Calidad del Aire ")
st.plotly_chart(fig, use_container_width=True)

# Bar Chart - Estaciones con mayor AQI promedio
top_municipios = datos_filtrados.sort_values("Indice de Calidad del Aire", ascending=False)
fig = px.bar(top_municipios, x="Estacion", y="Indice de Calidad del Aire", color="Contaminante Prevalente",
             title="Estaciones con mayor AQI promedio")
st.plotly_chart(fig)

# Promedio de AQI por municipio (Bar Chart)
bar_chart = px.bar(
    datos_filtrados.groupby('Municipio')['Indice de Calidad del Aire'].mean().reset_index(),
    x='Municipio',
    y='Indice de Calidad del Aire',
    title='Promedio de AQI por Municipio',
    labels={'Municipio': 'Municipio', 'Indice de Calidad del Aire': 'AQI Promedio'},
)
st.plotly_chart(bar_chart, use_container_width=True)

# Boxplot: ver la dispersión de valores de AQI por cada contaminante
box_plot = px.box(
    datos_filtrados,
    x='Contaminante Prevalente',
    y='Indice de Calidad del Aire',
    title='Distribución del AQI por Contaminante'
)
st.plotly_chart(box_plot, use_container_width=True)

# Pie chart por contaminantes prevalentes
pie_chart = px.pie(
    datos_filtrados,
    names='Contaminante Prevalente',
    title='Proporción de Contaminantes Prevalentes'
)
st.plotly_chart(pie_chart)


# --- MAPA INTERACTIVO CDMX ---
# Hacer join entre aqi_cdmx (que sí tiene lat/lon) y df_con_municipios
# --- Filtro combinado para el mapa de puntos ---
aqi_join = aqi_cdmx.merge(
    df_con_municipios,
    left_on="ESTACION",
    right_on="ESTACION",
    how="left"
)


aqi_filtrado = aqi_join.copy()

# Preparar columnas
aqi_filtrado = aqi_filtrado.rename(columns={ "ESTACION": "Estacion", "AQI_x": "Indice de Calidad del Aire", "TIPO_CONTAMINANTE_x": "Contaminante Prevalente", "latitud": "lat", "longitud": "lon", "NOM_MUN": "Municipio" })

aqi_filtrado = aqi_filtrado[['Estacion','Indice de Calidad del Aire','Contaminante Prevalente','lat','lon','Municipio']]


if municipio_seleccionado != "Todos":
    aqi_filtrado = aqi_filtrado[aqi_filtrado["Municipio"] == municipio_seleccionado]

if contaminante_seleccionado != "Todos":
    aqi_filtrado = aqi_filtrado[aqi_filtrado["Contaminante Prevalente"] == contaminante_seleccionado]



# Crear mapa base
mapa = folium.Map(location=[19.4326, -99.1332], zoom_start=11)

# paleta para AQI según min/max reales
# --- COLOMAP Verde → Amarillo → Rojo ---
colormap = cm.LinearColormap(
    colors=["green", "yellow", "red"],
    vmin=aqi_mapa["Indice de Calidad del Aire"].min(),
    vmax=aqi_mapa["Indice de Calidad del Aire"].max(),
    caption="Índice de Calidad del Aire (AQI)"
)



# --- Marcadores con popup ---
for _, row in aqi_mapa.iterrows():
    lat = row["lat"]
    lon = row["lon"]
    aqi = row["Indice de Calidad del Aire"]

    popup_text = (
        f"<b>Estación:</b> {row['Estacion']}<br>"
        f"<b>AQI:</b> {aqi}<br>"
    )

    folium.CircleMarker(
        location=(lat, lon),
        radius=7,
        color=colormap(aqi),
        fill=True,
        fill_color=colormap(aqi),
        fill_opacity=0.85,
        popup=folium.Popup(popup_text, max_width=300)
    ).add_to(mapa)
# Añadir legend nativo
colormap.add_to(mapa)
# Mostrar el mapa
st.subheader("Mapa Interactivo del AQI por Estación")
st_folium(mapa, width=700, height=700)



#Mapa interactivo raster
for nombre, (path, var) in archivos.items():
    gdf = leer_contaminante_raster(path, var)
    gdf = gpd.sjoin(gdf, cdmx, predicate="within")  # quedarse solo con CDMX
    gdfs.append(gdf[["lon", "lat", var]])

gdf_final = reduce(lambda left, right: pd.merge(left, right, on=["lon","lat"], how="outer"), gdfs)

gdf_final = gpd.GeoDataFrame(
    gdf_final,
    geometry=gpd.points_from_xy(gdf_final["lon"], gdf_final["lat"]),
    crs="EPSG:4326"
)

gdf_final["total_contaminacion"] = gdf_final[
    ["carbonmonoxide_total_column",
     "nitrogendioxide_tropospheric_column",
     "sulfurdioxide_total_vertical_column",
     "ozone_total_vertical_column",
     "aerosol_mid_pressure"]
].sum(axis=1)


gdf_final["promedio"] = gdf_final[
    ["carbonmonoxide_total_column",
     "nitrogendioxide_tropospheric_column",
     "sulfurdioxide_total_vertical_column",
     "ozone_total_vertical_column",
     "aerosol_mid_pressure"]
].mean(axis=1)


gdf_final["indice_normalizado"] = (
    (gdf_final["total_contaminacion"] - gdf_final["total_contaminacion"].min()) /
    (gdf_final["total_contaminacion"].max() - gdf_final["total_contaminacion"].min())
)

mapa_raster = folium.Map(location=[19.4326, -99.1332], zoom_start=10)

# Preparar datos para heatmap
heat_data = [
    [row['lat'], row['lon'], row['indice_normalizado']]
    for _, row in gdf_final.dropna(subset=["indice_normalizado"]).iterrows()
]

# Agregar heatmap
HeatMap(
    heat_data,
    radius=12,   # tamaño del punto
    blur=15,
    max_zoom=1
).add_to(mapa_raster)

MousePosition(position="topright", separator=" : ", prefix="Lat/Lon").add_to(mapa_raster)

paleta_norm = linear.YlGnBu_09.scale(0.0, 1.0)   # o el esquema que prefieras
paleta_norm.caption = "Índice Normalizado (0 = limpio, 1 = más contaminado)"

paleta_norm.add_to(mapa_raster)
   

# Mostrar el mapa dentro de Streamlit
st.subheader("Mapa Interactivo del AQI de los contaminantes CO, NO2, SO2, O3, AER")
st_data = st_folium(mapa_raster, width=700, height=700)
