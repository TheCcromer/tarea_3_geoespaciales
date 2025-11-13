# Tarea # 3 - Ciencias de Datos Geoespaciales

## Estudiantes

- Edwin Josué Brenes Cambronero, B51187
- Carlos Luis Ureña Alfaro, B77808

## Descripción del dataset

El conjunto de datos corresponde a mediciones de contaminantes atmosféricos registradas por las estaciones de monitoreo de la Ciudad de México (CDMX). Cada estación reporta concentraciones horarias de distintos contaminantes criterio, tales como CO, NO₂, O₃, PM2.5 y SO₂, entre otros.

Además, el dataset se complementa con la información geográfica de cada estación (latitud y longitud), lo que permite convertir los datos en un GeoDataFrame y realizar análisis espaciales. Con estas variables se calcula el Índice de Calidad del Aire (AQI), que cuantifica el nivel de contaminación en una escala estándar y permite evaluar la calidad del aire en diferentes zonas y momentos del año.

Los datos provienen de archivos oficiales (en formato XLS) correspondientes a cada contaminante, y fueron procesados para obtener promedios por ventana de tiempo y estación.

#Descripción de las columnas

| Columna                                | Descripción                                                                                                              |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **FECHA**                              | Fecha en la que se registró la medición.                                                                                 |
| **HORA**                               | Hora del día correspondiente al registro original (antes de agrupar por ventanas de tiempo).                             |
| **ESTACION**                           | Código de la estación de monitoreo (por ejemplo, ACO, MER, TLI, etc.).                                                   |
| **TIPO_CONTAMINANTE**                  | Contaminante medido (CO, NO₂, O₃, Pm2.5 o SO₂).                                                                          |
| **CANTIDAD_CONTAMINANTE**              | Valor promedio de concentración del contaminante, en la unidad correspondiente.                                          |
| **VENTANA_TIEMPO**                     | Agrupación temporal usada para calcular promedios (por ejemplo, cada 8 horas para CO, cada hora para NO₂, O₃ y SO₂).     |
| **AQI**                                | Índice de Calidad del Aire calculado a partir de la concentración del contaminante y los rangos establecidos por la EPA. |
| **AQI_CATEGORY**                       | Categoría cualitativa asociada al AQI (por ejemplo: Buena, Moderada, Dañina para grupos sensibles, etc.).                |
| **latitud**                            | Coordenada geográfica de la estación de monitoreo (norte-sur).                                                           |
| **longitud**                           | Coordenada geográfica de la estación de monitoreo (este-oeste).                                                          |
| **geometry**                           | Columna geométrica (punto) utilizada en el GeoDataFrame para representar espacialmente la ubicación de cada estación.    |
| **TRIMESTRE** _(derivada de la fecha)_ | Estación del año calculada (I, II, III, IV).                                                                             |

# Problema a resolver

Mediante el conjunto de datos utilizado y, los gráficos y mapas, se busca responder las siguientes preguntas:

1. ¿Cuáles son los municipios de Ciudad México con menores y mayores índices de contaminación en el aire (en promedio) durante el año 2024?
2. ¿Cuál es el contaminante qué produce mayor (AQI) en la Ciudad de México y en cuál municipio se localiza dicho valor?
