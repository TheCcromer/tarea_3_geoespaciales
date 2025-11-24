import geopandas as gpd
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import MiniMap, MousePosition, Fullscreen
from folium.plugins import HeatMap
import streamlit as st
from pathlib import Path
from util import corregir_acentos, remover_acentos
from functools import reduce
from data_generation import leer_contaminante_raster
import branca.colormap as cm

# ---------------------------
# Configuración y rutas
# ---------------------------
pd.set_option('display.float_format', '{:,.2f}'.format)
BASE_DIR = Path(__file__).resolve().parent
AQI_DATA_PATH = BASE_DIR / "data" / "valores_contaminantes_por_estaciones_cdmx.csv"

archivos = {
    "CO":  (BASE_DIR / "data" / "CO.nc",  "carbonmonoxide_total_column"),
    "NO2": (BASE_DIR / "data" / "NO2.nc", "nitrogendioxide_tropospheric_column"),
    "SO2": (BASE_DIR / "data" / "SO2.nc", "sulfurdioxide_total_vertical_column"),
    "O3":  (BASE_DIR / "data" / "O3.nc",  "ozone_total_vertical_column"),
    "AER": (BASE_DIR / "data" / "AER.nc","aerosol_mid_pressure")
}

# ---------------------------
# Helpers con caching
# ---------------------------
@st.cache_data
def cargar_aqi_csv(path):
    df = pd.read_csv(path, encoding='latin-1')
    # Normalizar nombres de columnas por si acaso
    df.columns = [c.strip() for c in df.columns]
    return gpd.GeoDataFrame(df)

@st.cache_data
def cargar_municipios(shp_path):
    mx = gpd.read_file(shp_path)
    mx['NOM_ENT'] = mx['NOM_ENT'].apply(remover_acentos)
    cdmx = mx[(mx['NOM_ENT'] == 'Ciudad de MAxico') | (mx['NOM_ENT'] == 'MAxico')]
    return cdmx

@st.cache_data
def cargar_rasters_filtrados(archivos_dict, cdmx_gdf):
    """
    Lee cada raster (.nc) con tu función leer_contaminante_raster,
    hace spatial join con cdmx y devuelve lista de dataframes con lon/lat/valor.
    """
    gdfs_local = []
    for nombre, (path, var) in archivos_dict.items():
        try:
            gdf = leer_contaminante_raster(path, var)
            # Asegurar columnas lon/lat existen
            if 'lon' not in gdf.columns or 'lat' not in gdf.columns:
                # intenta columnas alternativas
                if 'longitude' in gdf.columns and 'latitude' in gdf.columns:
                    gdf = gdf.rename(columns={'longitude':'lon','latitude':'lat'})
                else:
                    st.warning(f"No se encontraron lon/lat en {nombre} -> se omite")
                    continue
            # Quedarse solo con CDMX mediante spatial join (puede ser costoso)
            gdf = gpd.sjoin(gdf, cdmx_gdf, predicate="within", how="inner")
            # Seleccionar solo lon, lat, variable
            gdfs_local.append(gdf[['lon', 'lat', var]])
        except Exception as e:
            st.warning(f"Error procesando {nombre}: {e}")
    return gdfs_local

# ---------------------------
# Carga principal de datos
# ---------------------------
gdf_total = cargar_aqi_csv(AQI_DATA_PATH)  # GeoDataFrame con AQI por estaciones
cdmx = cargar_municipios(BASE_DIR / "data" / "mun21gw" / "mun21gw.shp")

# ---------------------------
# Procesamiento de AQI por estación (promedio anual)
# ---------------------------
promedios_anuales = (
    gdf_total
    .groupby(['ESTACION', 'TIPO_CONTAMINANTE', 'latitud', 'longitud'], as_index=False)['AQI']
    .mean()
)

# Para cada estación tomar el contaminante que reportó el AQI máximo (estación representativa)
aqi_anual_estaciones = (
    promedios_anuales.loc[promedios_anuales.groupby('ESTACION')['AQI'].idxmax()]
    .reset_index(drop=True)
)

aqi_cdmx = gpd.GeoDataFrame(
    aqi_anual_estaciones,
    geometry=gpd.points_from_xy(aqi_anual_estaciones['longitud'], aqi_anual_estaciones['latitud']),
    crs="EPSG:4326"
)

# Spatial join para asignar municipio
df_con_municipios = gpd.sjoin(aqi_cdmx, cdmx, how="left", predicate="within")
df_con_municipios = df_con_municipios[['ESTACION','NOM_MUN','TIPO_CONTAMINANTE','AQI']]
df_con_municipios['NOM_MUN'] = df_con_municipios['NOM_MUN'].apply(corregir_acentos)

# Filtrado por municipio (UI)
lista_municipios = sorted(df_con_municipios['NOM_MUN'].dropna().unique().tolist())
opciones_municipios = ['Todos'] + lista_municipios
municipio_seleccionado = st.sidebar.selectbox('Selecciona un municipio', opciones_municipios)

if municipio_seleccionado != 'Todos':
    datos_filtrados = df_con_municipios[df_con_municipios['NOM_MUN'] == municipio_seleccionado]
else:
    datos_filtrados = df_con_municipios.copy()

# Mostrar tabla
st.subheader('AQI (Air Quality Index) — Promedio Anual por Municipio')
datos_filtrados_display = datos_filtrados.rename(columns={
    'ESTACION': 'Estación',
    'NOM_MUN': 'Municipio',
    'TIPO_CONTAMINANTE': 'Contaminante Prevalente',
    'AQI': 'Índice de Calidad del Aire'
})
st.dataframe(datos_filtrados_display, hide_index=True)

# ---------------------------
# Gráficos interactivos (Plotly)
# ---------------------------
st.subheader("Gráficos relacionados al Índice de Calidad del Aire")

aqi_prom = gdf_total.groupby('TIPO_CONTAMINANTE')['AQI'].mean().reset_index()
fig = px.bar(aqi_prom, x='TIPO_CONTAMINANTE', y='AQI',
             title='Valores promedio de AQI por contaminante',
             labels={'TIPO_CONTAMINANTE': 'Contaminante', 'AQI': 'AQI Promedio'})
fig.update_yaxes(tickformat=",d")
st.plotly_chart(fig, use_container_width=True)

# Top estaciones y otros gráficos
top_municipios = datos_filtrados.sort_values("AQI", ascending=False)
fig2 = px.bar(top_municipios, x="ESTACION", y="AQI", color="TIPO_CONTAMINANTE",
              title="Estaciones con mayor AQI promedio")
st.plotly_chart(fig2)

bar_chart = px.bar(datos_filtrados.groupby('NOM_MUN')['AQI'].mean().reset_index(),
                   x='NOM_MUN', y='AQI', title='Promedio de AQI por Municipio',
                   labels={'NOM_MUN': 'Municipio', 'AQI': 'AQI Promedio'})
st.plotly_chart(bar_chart, use_container_width=True)

box_plot = px.box(datos_filtrados, x='TIPO_CONTAMINANTE', y='AQI', title='Distribución del AQI por Contaminante')
st.plotly_chart(box_plot, use_container_width=True)

pie_chart = px.pie(datos_filtrados, names='TIPO_CONTAMINANTE', title='Proporción de Contaminantes Prevalentes')
st.plotly_chart(pie_chart)

# ---------------------------
# Preparar datos raster / satélite y combinar contaminantes
# ---------------------------
st.subheader("Mapa interactivo — integración de productos satelitales")

gdfs = cargar_rasters_filtrados(archivos, cdmx)

# Si no hay datos raster, mostrar aviso
if not gdfs:
    st.warning("No se pudieron cargar los datos raster. Revisa que los archivos existan y que 'leer_contaminante_raster' funcione.")
else:
    # Combinar por lon/lat
    gdf_final = reduce(lambda left, right: pd.merge(left, right, on=["lon","lat"], how="outer"), gdfs)
    gdf_final = gpd.GeoDataFrame(
        gdf_final,
        geometry=gpd.points_from_xy(gdf_final["lon"], gdf_final["lat"]),
        crs="EPSG:4326"
    )

    # Asegurar que las columnas existan (evitar KeyError)
    pollutant_cols = [v for _, v in archivos.values()]
    existing_pollutants = [c for c in pollutant_cols if c in gdf_final.columns]
    if not existing_pollutants:
        st.error("No se encontraron las variables de contaminantes en los datos raster combinados.")
    else:
        # Calcular indicadores simples
        gdf_final["total_contaminacion"] = gdf_final[existing_pollutants].sum(axis=1)
        gdf_final["promedio"] = gdf_final[existing_pollutants].mean(axis=1)
        gdf_final["indice_normalizado"] = (
            (gdf_final["total_contaminacion"] - gdf_final["total_contaminacion"].min()) /
            (gdf_final["total_contaminacion"].max() - gdf_final["total_contaminacion"].min())
        )

        # Crear mapa base
        mapa_raster = folium.Map(location=[19.4326, -99.1332], zoom_start=10, tiles="CartoDB positron")

        # --- MiniMap (contexto) ---
        minimap = MiniMap(toggle_display=True, position="bottomright")
        mapa_raster.add_child(minimap)

        # --- Fullscreen ---
        Fullscreen(position='topleft').add_to(mapa_raster)

        # --- Mouse position (coord display) ---
        MousePosition(position="topright", separator=" : ", prefix="Lat/Lon").add_to(mapa_raster)

        # --- Crear colormap (branca) para la leyenda ---
        colormap = cm.LinearColormap(['blue','green','yellow','orange','red'],
                                    vmin=0, vmax=1,
                                    caption='Índice Normalizado (0 - limpio, 1 - más contaminado)')
        colormap.add_to(mapa_raster)

        # --- Capa de heatmap general (total) dentro de FeatureGroup para control de capas ---
        fg_total = folium.FeatureGroup(name="Heatmap — Total (todos contaminantes)", show=True)
        heat_data_total = [[row['lat'], row['lon'], row['indice_normalizado']] for _, row in gdf_final.dropna(subset=["indice_normalizado"]).iterrows()]
        HeatMap(heat_data_total, radius=12, blur=15, max_zoom=12).add_to(fg_total)
        mapa_raster.add_child(fg_total)

        # --- Capas individuales por contaminante (si existen) ---
        for pollutant in existing_pollutants:
            fg = folium.FeatureGroup(name=f"Heatmap — {pollutant}", show=False)
            heat_data = [[row['lat'], row['lon'], row[pollutant]] for _, row in gdf_final.dropna(subset=[pollutant]).iterrows()]
            HeatMap(heat_data, radius=10, blur=14, max_zoom=12).add_to(fg)
            mapa_raster.add_child(fg)

        # --- Añadir puntos con popups detallados (opcional, en una capa) ---
        fg_puntos = folium.FeatureGroup(name="Puntos — detalles", show=False)
        for _, row in gdf_final.dropna(subset=["lon","lat"]).iterrows():
            popup_html = "<div style='font-size:12px'>"
            for pollutant in existing_pollutants:
                val = row.get(pollutant)
                popup_html += f"<b>{pollutant}:</b> {val:.4f}<br>" if pd.notna(val) else f"<b>{pollutant}:</b> N/A<br>"
            popup_html += f"<b>Total norm:</b> {row['indice_normalizado']:.3f}<br>"
            popup_html += "</div>"
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=3,
                color=None,
                fill=True,
                fill_opacity=0.7,
                fill_color=colormap(row['indice_normalizado']) if pd.notna(row['indice_normalizado']) else "#000000",
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(fg_puntos)
        mapa_raster.add_child(fg_puntos)

        # --- Layer control para activar/desactivar capas ---
        folium.LayerControl(collapsed=False).add_to(mapa_raster)

        # --- Mostrar resultado en Streamlit ---
        st.subheader("Mapa Interactivo del AQI (satélite) — Heatmaps y capas")
        st_data = st_folium(mapa_raster, width=1000, height=600)

        # Pequeña tabla resumen al pie
        st.markdown("**Resumen**")
        st.write(f"Total puntos: {len(gdf_final)}")
        st.write("Capas disponibles: Total + " + ", ".join(existing_pollutants) + " + Puntos (popup)")
