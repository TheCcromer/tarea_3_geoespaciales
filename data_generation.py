# Logica utilizada para cargar los datos en tarea #2
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
from pathlib import Path
import h5py

# Estructuras de datos
lista_contaminantes = ["CO", "NO2", "O3", "PM25", "SO2"]

cdmx_stations = [
    'ACO', 'AJM', 'BJU', 'CAM', 'CCA', 'CHO', 'CUA', 'FAC', 'HGM',
    'INN', 'IZT', 'LLA', 'LPR', 'MER', 'MGH', 'MPA', 'PED', 'SAG',
    'SAC', 'SFE', 'SJA', 'TAH', 'TLI', 'UAX', 'UIZ'
]

dict_contaminantes = {} # Para guardar los df de cada uno de los contaminantes

def leer_contaminante_raster(path, variable_name, qa_threshold=0.5):
    
    with h5py.File(path, "r") as f:
        name = "PRODUCT/" + variable_name
        values = f[name][:].flatten()
        lat = f["PRODUCT/latitude"][:].flatten()
        lon = f["PRODUCT/longitude"][:].flatten()
        qa = f["PRODUCT/qa_value"][:].flatten()


    df = pd.DataFrame({
        "lat": lat,
        "lon": lon,
        variable_name: values,
        "qa_value": qa
    })

    # Filtrar QA
    df = df[df["qa_value"] >= qa_threshold]

    # Convertir a GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326"
    )

    return gdf
  
def carga_contaminante(contaminante):
  csv_path = BASE_DIR / "data" / f'2024{contaminante}.csv'
  df = pd.read_csv(csv_path)
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

#Calculos
def cargar_dict_contaminantes():
    coordenadas_est = pd.read_csv(BASE_DIR / "data" / "cat_estacion.csv", encoding='latin-1')
    coordenadas_est = coordenadas_est.rename(columns={'cve_estac': 'ESTACION'})
    coordenadas_est = coordenadas_est[['ESTACION','longitud', 'latitud']]
    rangos_aqi = pd.read_csv(BASE_DIR / "data" / "aqi_breakpoints.csv")
    rangos_aqi = rangos_aqi[['TIPO_CONTAMINANTE', 'AQI_CATEGORY', 'Low_AQI','High_AQI','Low_Breakpoint','High_Breakpoint']]

    for contaminante in lista_contaminantes:
        dict_contaminantes[contaminante] = carga_contaminante(contaminante)
        transformacion_df(dict_contaminantes,contaminante,coordenadas_est)
        calculo_AQI(dict_contaminantes,contaminante,rangos_aqi)
        agrupar_por_dia(dict_contaminantes,contaminante)
    
    pd.concat(dict_contaminantes.values(), ignore_index=True).to_csv("data/valores_contaminantes_por_estaciones_cdmx.csv")