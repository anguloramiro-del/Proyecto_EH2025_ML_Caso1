# Complemento municipal del Caso 1: datos reales y perfiles exploratorios

Este módulo agrega un análisis territorial real de 343 municipios y TIOC del Censo de Población y Vivienda 2024. Es un complemento independiente del modelo individual EH2025. No asigna municipios a personas de la encuesta, no utiliza municipios de nacimiento o migración como residencia actual y no estima tasas municipales a partir de una muestra sin representatividad municipal.

## Cómo integrarlo y ejecutarlo

Copiar `src/municipal.py` al proyecto. Conservar los indicadores oficiales preparados en `data/municipal/municipios_censo2024_indicadores.csv` y la geometría verificada en `data/bolivia_municipios_2024.geojson`. La función pública es `create_municipal_analysis(project_root)`; también puede ejecutarse `python -m src.municipal --project-root .`. Los resultados se guardan en `outputs/municipal/`. El código no contiene rutas de la computadora del autor.

Se requieren las dependencias ya utilizadas por el proyecto y `shapely` para verificar geometrías. Las figuras HTML llevan Plotly incorporado y no requieren descargar mapas, claves ni servicios cartográficos para abrirse. Incluyen enlaces de atribución; seguir esos enlaces sí requiere conexión. La inspección automatizada de su estructura verifica las dos vistas del mapa y sus trazas. La apariencia de los PNG fue inspeccionada; eso no sustituye una prueba manual del hover y del selector en navegador.

## Dataset procesado entregado

`dataset_municipal_procesado_2024.csv` y `.parquet` contienen 343 filas y 47 columnas. Las 38 columnas originales están preservadas; se añaden el complemento de fuente mejorada de agua, cuatro variables estandarizadas, dos etiquetas de perfil y dos componentes principales. Son los datos reales utilizados en el agrupamiento municipal, no datos simulados ni un archivo de resultados individuales EH2025. `diccionario_dataset_municipal_procesado.csv` explica cada columna y conserva la trazabilidad de los cuadros y columnas Excel del INE. El diccionario es documentación estática; los datos, perfiles, figuras y auditoría se regeneran con el módulo.

Se conservan las variables de entrada sin faltantes: no asistencia educativa de 12–17 años, ruralidad de 12–17 años, promedio de años de estudio de población de 19 años o más y porcentaje de población de 12–17 años sin fuente mejorada de agua. Las covariables de áreas urbanas o rurales inexistentes conservan sus faltantes originales y no intervienen en KMeans. No se imputa ningún valor. Los códigos municipales se conservan como texto de seis dígitos.

## Método y lectura de resultados

StandardScaler centra y escala las cuatro variables sobre las 343 jurisdicciones con igual peso y desviación poblacional. KMeans compara k=2 a k=6, usa semilla 2026 y 20 inicializaciones; la regla de selección del proyecto maximiza silhouette y exige al menos diez jurisdicciones por grupo. Gana k=4 con silhouette 0,318886. k=5 obtiene 0,318727: la diferencia de 0,000160 es muy pequeña. La selección describe una solución exploratoria, no demuestra un número verdadero y único de perfiles.

Los perfiles se ordenan por su media municipal de no asistencia: P1=82, P2=157, P3=41 y P4=63 jurisdicciones. Las medias municipales de no asistencia son 6,59%, 7,22%, 8,86% y 18,71%, respectivamente. La tasa censal agrupada se calcula aparte con conteos y denominador educativo; no se confunde con la media de municipios. P4 puede orientar una primera verificación local de 63 jurisdicciones, sin convertir esa lista en beneficiarios ni asignaciones automáticas de presupuesto. P3 aporta un contexto distinto de menor acceso a fuentes mejoradas de agua. Estos patrones no prueban causas ni efectos de una intervención.

La no asistencia es una de las variables utilizadas para crear los perfiles; su separación entre grupos no es validación predictiva independiente. No asistencia actual no equivale a abandono escolar longitudinal. El ARI de 0,982755 y 0,992199 con semillas 2027 y 2028 comprueba sensibilidad a la inicialización, sin medir estabilidad temporal. Los dos primeros componentes principales explican 48,07% y 25,40% de la varianza estandarizada (73,47% acumulada).

## Fuentes y límites de interpretación

- INE, Censo 2024, tabulados de educación: https://www.ine.gob.bo/index.php/censos-educacion/
- INE, Censo 2024, indicadores de vivienda y servicios: https://www.ine.gob.bo/index.php/estadisticas-economicas/censos-indicadores/
- UDAPE, Atlas 2025, capa pública de referencia municipal/TIOC: https://sigudape.udape.gob.bo/atlas2025/
- Acceso y preparación de las fuentes: 15 de noviembre de 2026. Conservar los manifiestos, notas del parser, equivalencias auditadas y diccionarios originales facilitados con los insumos.

Los indicadores combinan universos distintos: 1.265.155 personas en el denominador educativo de asistencia de 12–17 años; 1.270.984 en el cuadro de escolaridad de esa edad y 1.272.725 en servicios de viviendas particulares de esa edad. El promedio de estudio tiene 7.350.282 personas de 19 años o más. Son características contextuales con sus propios denominadores; no deben recalcularse unas usando los denominadores de otras. Fuente mejorada de agua no equivale a potabilidad certificada.

La geometría permite visualización geoestadística orientativa; no define límites legales, no se utiliza para calcular superficies ni para asignar personas. Se atribuye a UDAPE sin afirmar una licencia abierta ni una autorización irrestricta de redistribución. La simplificación conserva geometrías individuales válidas y correspondencia de códigos, pero no convierte la cobertura en una delimitación legal/topológica perfecta.

El dataset municipal es agregado y público en su fuente. Los registros individuales procesados EH2025 se entregan en un complemento académico restringido separado y conservan las condiciones de acceso de ANDA. Ninguna fila individual forma parte de este módulo municipal.
