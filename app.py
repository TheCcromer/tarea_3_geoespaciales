import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import TimestampedGeoJson
from folium.plugins import HeatMap
import seaborn as sns
import matplotlib.pyplot as plt
import streamlit as st
from pathlib import Path
from util import corregir_acentos, remover_acentos
from functools import reduce
from data_generation import leer_contaminante_raster


# Configuración 
pd.set_option('display.float_format', '{:,.2f}'.format)

# Obtener ruta del proyecto
BASE_DIR = Path(__file__).resolve().parent
AQI_DATA_PATH = BASE_DIR / "data" / "valores_contaminantes_por_estaciones_cdmx.csv"

gdf_total = gpd.GeoDataFrame(pd.read_csv(AQI_DATA_PATH, encoding='latin-1'))

#Archivos raster
archivos = {
    "CO":  ("data/CO.nc",  "carbonmonoxide_total_column"),
    "NO2": ("data/NO2.nc", "nitrogendioxide_tropospheric_column"),
    "SO2": ("data/SO2.nc", "sulfurdioxide_total_vertical_column"),
    "O3":  ("data/O3.nc",  "ozone_total_vertical_column"),
    "AER": ("data/AER.nc","aerosol_mid_pressure")
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

if municipio_seleccionado != 'Todos':
    # Filtrar los datos para el país seleccionado
    datos_filtrados = df_con_municipios[df_con_municipios['NOM_MUN'] == municipio_seleccionado]
else:
    # No aplicar filtro
    datos_filtrados = df_con_municipios.copy()

# Mostrar la tabla
st.subheader('AQI (Air Quality Index) Promedio Anual por Municipio de la Ciudad México')
datos_filtrados = datos_filtrados.rename(columns={
    'ESTACION': 'Estación',
    'NOM_MUN': 'Municipio',
    'TIPO_CONTAMINANTE': 'Contaminante Prevalente',
    'AQI': 'Índice de Calidad del Aire'
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
top_municipios = datos_filtrados.sort_values("Índice de Calidad del Aire", ascending=False)
fig = px.bar(top_municipios, x="Estación", y="Índice de Calidad del Aire", color="Contaminante Prevalente",
             title="Estaciones con mayor AQI promedio")
st.plotly_chart(fig)

# Promedio de AQI por municipio (Bar Chart)
bar_chart = px.bar(
    datos_filtrados.groupby('Municipio')['Índice de Calidad del Aire'].mean().reset_index(),
    x='Municipio',
    y='Índice de Calidad del Aire',
    title='Promedio de AQI por Municipio',
    labels={'Municipio': 'Municipio', 'Índice de Calidad del Aire': 'AQI Promedio'},
)
st.plotly_chart(bar_chart, use_container_width=True)

# Boxplot: ver la dispersión de valores de AQI por cada contaminante
box_plot = px.box(
    datos_filtrados,
    x='Contaminante Prevalente',
    y='Índice de Calidad del Aire',
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


#Mapa Interactivo CDMX
aqi_mapa = aqi_cdmx.rename(columns={
    "ESTACION": "Estación",
    "AQI": "Índice de Calidad del Aire",
    "TIPO_CONTAMINANTE": "Contaminante Prevalente"
})
mapa = aqi_mapa.explore(
    column="Índice de Calidad del Aire",  # Columna que define el color
    cmap="RdYlGn_r",
    legend=True, # Muestra barra de colores
    marker_kwds=dict(radius=8, fillOpacity=0.8),  # Opciones del marcador
    tooltip=["Estación", "Índice de Calidad del Aire", "Contaminante Prevalente"],  # Info al pasar el mouse
)
# Mostrar el mapa dentro de Streamlit
st.subheader("Mapa Interactivo del AQI por Estación")
st_data = st_folium(mapa, width=1000, height=600)


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


# Mostrar el mapa dentro de Streamlit
st.subheader("Mapa Interactivo del AQI de los contaminantes CO, NO2, SO2, O3, AER")
st_data = st_folium(mapa_raster, width=1000, height=600)