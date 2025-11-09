import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import folium
from folium.plugins import TimestampedGeoJson
import seaborn as sns
import matplotlib.pyplot as plt
import streamlit as st
import unidecode
import unicodedata


#Configuración 
pd.set_option('display.float_format', '{:,.2f}'.format)


#Funciones

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

def obtener_trimestre(fecha):
  mes = fecha.month
  if mes in [1, 2, 3]:
    return 'Trimestre I'
  elif mes in [4, 5, 6]:
    return 'Trimestre II'
  elif mes in [7, 8, 9]:
    return 'Trimestre III'
  else:
    return 'Trimestre IV'

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
def remove_accents(input_str):
    import unicodedata
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nkfd_form.encode('ASCII', 'ignore')
    return only_ascii.decode('utf-8')
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

#Filtrado

# Obtener la lista de países únicos
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
    datos_filtrados = join[join['País'] == municipio_seleccionado]
else:
    # No aplicar filtro
    datos_filtrados = join.copy()

# Mostrar la tabla
st.subheader('AQI promedio anual de contaminantes por municipio')
st.dataframe(datos_filtrados, hide_index=True)


#Gráfico de Barras para valores de AQI por contaminante

aqi_prom = gdf_total.groupby('TIPO_CONTAMINANTE')['AQI'].mean().reset_index()

fig = px.bar(
    aqi_prom,
    x='TIPO_CONTAMINANTE',
    y='AQI',
    title='Suma de población por continente',
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
    title=dict(
        x=0.5,  # Centrar el título
        font=dict(size=20)
    ),
    xaxis_title=dict(
        font=dict(size=16)
    ),
    yaxis_title=dict(
        font=dict(size=16)
    )
)
# Despliegue del gráfico
fig.show()


#Mapa Interactivo CDMX

# HTML generado guardado en output/aqi_cdmx.html

aqi_cdmx.explore(
    column="AQI",              # Columna que define el color
    cmap="RdYlGn_r",
    legend=True,               # Muestra barra de colores
    marker_kwds=dict(radius=8, fillOpacity=0.8),  # Opciones del marcador
    tooltip=["ESTACION", "AQI", "TIPO_CONTAMINANTE"],  # Info al pasar el mouse
)



