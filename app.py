import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import TimestampedGeoJson
import seaborn as sns
import matplotlib.pyplot as plt
import streamlit as st
import unidecode
import unicodedata


#Configuración 
pd.set_option('display.float_format', '{:,.2f}'.format)


#Funciones

def corregir_texto(texto):
    try:
        return texto.encode('latin1').decode('utf-8')
    except Exception:
        return texto

def remove_accents(input_str):
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nkfd_form.encode('ASCII', 'ignore')
    return only_ascii.decode('utf-8')

def carga_contaminante(contaminante):
  df = pd.read_csv(f'data/2024{contaminante}.csv')
  cols_to_keep = ['FECHA', 'HORA'] + cdmx_stations
  df = df[[col for col in cols_to_keep if col in df.columns]] # Filtracion de unicamente estaciones importantes
  return df

def transformacion_df(dict_contaminantes, contaminante, coordenadas_est):
  dict_contaminantes[contaminante] = dict_contaminantes[contaminante].melt(
    id_vars=['FECHA', 'HORA'],   # columnas que permanecen fijas
    var_name='ESTACION',             # nuevo nombre para la columna que indica estacion
    value_name='CANTIDAD_CONTAMINANTE'        # nuevo nombre para la columna con los valores numéricos
  )
  dict_contaminantes[contaminante] = dict_contaminantes[contaminante][dict_contaminantes[contaminante]['CANTIDAD_CONTAMINANTE'] != -99]
  dict_contaminantes[contaminante]['TIPO_CONTAMINANTE'] = contaminante

    # Para O3 convertir de ppb a ppm
  if contaminante == 'O3':
    dict_contaminantes[contaminante]['CANTIDAD_CONTAMINANTE'] = dict_contaminantes[contaminante]['CANTIDAD_CONTAMINANTE'] / 1000

  if(contaminante == 'CO'): #8H
    dict_contaminantes[contaminante]['VENTANA_TIEMPO'] = ((dict_contaminantes[contaminante]['HORA']-1)// 8)+1
  elif (contaminante == 'NO2' or contaminante == 'O3' or contaminante == 'SO2'): #1H
    dict_contaminantes[contaminante]['VENTANA_TIEMPO'] = ((dict_contaminantes[contaminante]['HORA']-1)// 1)+1
  else: #24H
    dict_contaminantes[contaminante]['VENTANA_TIEMPO'] = ((dict_contaminantes[contaminante]['HORA']-1)// 24)+1


  dict_contaminantes[contaminante] = (
      dict_contaminantes[contaminante].groupby(["FECHA", "ESTACION", "TIPO_CONTAMINANTE", "VENTANA_TIEMPO"], as_index=False)
        .agg({"CANTIDAD_CONTAMINANTE": "mean"})
  )

  dict_contaminantes[contaminante] = pd.merge(dict_contaminantes[contaminante], coordenadas_est, on="ESTACION", how="left")

def calculo_AQI(dict_contaminantes, contaminante, rangos_aqi):
  dict_contaminantes[contaminante]['AQI'] = 0
  resultado = pd.merge(dict_contaminantes[contaminante], rangos_aqi, on='TIPO_CONTAMINANTE', how='left')
  resultado = resultado[(resultado['CANTIDAD_CONTAMINANTE'] >= resultado['Low_Breakpoint']) & (resultado['CANTIDAD_CONTAMINANTE'] <= resultado['High_Breakpoint'])]
  resultado = resultado[["FECHA", "ESTACION", 'longitud', 'latitud', "TIPO_CONTAMINANTE", "VENTANA_TIEMPO", "CANTIDAD_CONTAMINANTE", 'Low_AQI','High_AQI','Low_Breakpoint','High_Breakpoint', 'AQI_CATEGORY']]
  resultado["AQI"] = (
      (resultado["High_AQI"] - resultado["Low_AQI"])
      / (resultado["High_Breakpoint"] - resultado["Low_Breakpoint"])
      * (resultado["CANTIDAD_CONTAMINANTE"] - resultado["Low_Breakpoint"])
      + resultado["Low_AQI"]
  )
  dict_contaminantes[contaminante] = resultado[["FECHA", "ESTACION", "TIPO_CONTAMINANTE", "VENTANA_TIEMPO", "CANTIDAD_CONTAMINANTE", "AQI", 'AQI_CATEGORY', 'longitud', 'latitud']]


def convertir_geopandas(dict_contaminantes, contaminante):
  dict_contaminantes[contaminante] = gpd.GeoDataFrame(
    dict_contaminantes[contaminante],
    geometry=gpd.points_from_xy(dict_contaminantes[contaminante]['longitud'], dict_contaminantes[contaminante]['latitud']),
    crs="EPSG:4326"
  )

def agrupar_por_dia(dict_contaminantes,contaminante):
  dict_contaminantes[contaminante] = (
    dict_contaminantes[contaminante]
      .groupby(['FECHA', 'ESTACION', 'TIPO_CONTAMINANTE'], as_index=False)
      .agg({
      'CANTIDAD_CONTAMINANTE': 'mean',
      'AQI': 'mean',
      'longitud': 'first',
      'latitud': 'first',
      'AQI_CATEGORY': lambda x: x.mode()[0] if not x.mode().empty else None
      })
    )
  

#Estructuras de datos
lista_contaminantes = ["CO", "NO2", "O3", "PM25", "SO2"]

dict_contaminantes = {} #Va a guardar los df de cada uno de los contaminantes

cdmx_stations = [
    'ACO', 'AJM', 'BJU', 'CAM', 'CCA', 'CHO', 'CUA', 'FAC', 'HGM',
    'INN', 'IZT', 'LLA', 'LPR', 'MER', 'MGH', 'MPA', 'PED', 'SAG',
    'SAC', 'SFE', 'SJA', 'TAH', 'TLI', 'UAX', 'UIZ'
]

#Calculos

coordenadas_est = pd.read_csv('data/cat_estacion.csv', encoding='latin-1')
coordenadas_est = coordenadas_est.rename(columns={'cve_estac': 'ESTACION'})
coordenadas_est = coordenadas_est[['ESTACION','longitud', 'latitud']]
rangos_aqi = pd.read_csv('data/aqi_breakpoints.csv')
rangos_aqi = rangos_aqi[['TIPO_CONTAMINANTE', 'AQI_CATEGORY', 'Low_AQI','High_AQI','Low_Breakpoint','High_Breakpoint']]
for contaminante in lista_contaminantes:
  dict_contaminantes[contaminante] = carga_contaminante(contaminante)
  transformacion_df(dict_contaminantes,contaminante,coordenadas_est)
  calculo_AQI(dict_contaminantes,contaminante,rangos_aqi)
  agrupar_por_dia(dict_contaminantes,contaminante)

gdf_total = gpd.GeoDataFrame(pd.concat(dict_contaminantes.values(), ignore_index=True))


#Carga de Municipios CDMX

mx = gpd.read_file("data/mun21gw/mun21gw.shp")


mx['NOM_ENT'] = mx['NOM_ENT'].apply(remove_accents)


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
join = gpd.sjoin(aqi_cdmx, cdmx, how="left", predicate="within")

join = join[['ESTACION','NOM_MUN','TIPO_CONTAMINANTE','AQI']]
join['NOM_MUN'] = join['NOM_MUN'].apply(corregir_texto)
#Filtrado

# Obtener la lista de municipios únicos
lista_municipios = join['NOM_MUN'].unique().tolist()
lista_municipios.sort()

# Añadir la opción "Todos" al inicio de la lista
opciones_municipios = ['Todos'] + lista_municipios

# Crear el selectbox en la barra lateral
municipio_seleccionado = st.sidebar.selectbox(
    'Selecciona un municipio',
    opciones_municipios
)

# ----- Filtrar datos según la selección -----

if municipio_seleccionado != 'Todos':
    # Filtrar los datos para el país seleccionado
    datos_filtrados = join[join['NOM_MUN'] == municipio_seleccionado]
else:
    # No aplicar filtro
    datos_filtrados = join.copy()

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


