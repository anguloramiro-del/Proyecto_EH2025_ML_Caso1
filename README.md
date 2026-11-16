# No asistencia educativa en Bolivia: EH2025 y perfiles municipales del Censo 2024

![Estado](https://img.shields.io/badge/estado-an%C3%A1lisis%20ejecutado-green)
![Caso](https://img.shields.io/badge/caso-1-blue)
![Python](https://img.shields.io/badge/Python-3.12-blue)

Proyecto de ciencia de datos para orientar políticas de continuidad y revinculación educativa. Integra DuckDB, EDA automatizado, Random Forest, XGBoost y visualizaciones interactivas. El componente municipal está desarrollado con agregados oficiales de **343 municipios/TIOC del Censo 2024**, cartografía UDAPE, K-Means, PCA y un mapa interactivo.

Se distinguen dos unidades de análisis: adolescentes de 12 a 17 años de la EH2025 y municipios/TIOC del Censo 2024. No se asigna municipio actual a las personas EH ni se presentan tasas municipales como estimaciones de la encuesta. Las dos fuentes tienen años, universos y procedimientos diferentes; no constituyen una serie anual. La no asistencia observada no demuestra abandono longitudinal ni efectos causales.

## Abrir el trabajo

- [Informe final PDF](docs/Informe_Caso1_EH2025_Final.pdf).
- [Informe final Word editable](docs/Informe_Caso1_EH2025_Final.docx).
- [Explorador de resultados interactivos](docs/Explorar_resultados.html).
- [EDA automatizado YData-Profiling](outputs/eda_report.html).
- [Cuaderno completo](notebooks/03_Caso1_Completo.ipynb).
- [Dataset municipal procesado CSV](outputs/municipal/dataset_municipal_procesado_2024.csv) y [Parquet](outputs/municipal/dataset_municipal_procesado_2024.parquet).
- [Mapa municipal interactivo](outputs/municipal/mapa_municipal_2024.html).
- [Guía para publicar en GitHub y entregar en Moodle](docs/Entrega_en_GitHub.md).

Para explorar HTML, descargar y descomprimir el proyecto completo y abrir `docs/Explorar_resultados.html` en el navegador. La vista habitual de GitHub muestra el código del HTML. Mantener las carpetas en su ubicación para conservar sus enlaces.

## Qué decisiones permite sustentar

La propuesta se centra en identificar barreras y evaluar acciones de continuidad educativa, con revisión humana y registros educativos adicionales:

- Verificar la matrícula y asistencia de adolescentes de 16 y 17 años, con seguimiento propuesto a 30 y 60 días.
- Examinar los perfiles municipales de no asistencia, ruralidad, escolaridad adulta y acceso a fuente mejorada de agua antes de seleccionar intervenciones territoriales.
- Probar apoyos educativos y coordinación con servicios locales, midiendo cobertura, continuidad y revinculación.
- Validar los modelos con información nueva antes de utilizarlos en decisiones individuales.

Los perfiles municipales describen condiciones contextuales. No identifican beneficiarios ni prueban que una barrera particular cause la no asistencia. Cobertura operativa, presupuesto, responsables y metas requieren definición y validación institucional.

## Resultados y límites

**EH2025.** Se verificaron los siete módulos SAV recibidos contra el diccionario. Persona contiene 39.485 registros y 276 variables; Vivienda, 12.726 registros y 64 variables. El cruce DuckDB conserva las personas y la suma de pesos, sin claves vacías, duplicadas ni personas sin hogar asociado.

El universo analítico contiene 4.731 adolescentes, 169 con no asistencia. La tasa ponderada es 4,1569%; el IC95% aproximado ajustado es 2,8395–5,4742%, con CV de 16,15%. La linealización Taylor usa muestra completa, estratos y UPM; dos estratos solitarios requieren la convención explícita `adjust` y no se dispone de FPC. Los intervalos estrictos quedan nulos. Todos los dominios regionales presentan CV ajustado superior a 20%; el mapa de la encuesta no permite un ranking territorial firme. El EDA automatizado es no ponderado; las estimaciones descriptivas se calculan aparte con el diseño documentado.

**Modelos supervisados.** XGBoost se seleccionó por AP ponderada de validación cruzada: 0,1727 frente a 0,1555 de Random Forest. En la reserva, XGBoost obtiene AUC 0,7134 y AP 0,1096; Random Forest, AUC 0,7033 y AP 0,0841; la referencia AP es 0,0327. Ambos tienen recall y F1 iguales a cero al umbral 0,5, con 34 positivos entre 945 casos de prueba. El modelo no está validado como sistema operativo de alertas. La reserva no se empleó para ajustar el umbral.

**Municipios/TIOC, Censo 2024.** El conjunto municipal procesado contiene 343 filas y 47 columnas. El agrupamiento utiliza indicadores estandarizados de no asistencia de 12–17 años, ruralidad del mismo grupo, años promedio de estudio de población de 19 años o más y carencia de acceso a fuente mejorada de agua entre adolescentes. Una fuente mejorada no acredita por sí sola potabilidad. Se obtienen cuatro grupos de 82, 157, 41 y 63 municipios/TIOC; la selección es exploratoria porque la separación de cuatro y cinco grupos es muy cercana. Las dos primeras componentes principales explican aproximadamente 73,47% de la variación. El mapa representa los perfiles municipales completos, sin ubicar personas EH.

Los denominadores censales válidos difieren: asistencia de 12–17 años, 1.265.155 personas; escolaridad de ese grupo, 1.270.984; servicios en viviendas particulares de 12–17 años, 1.272.725. Las sumas de los 343 municipios/TIOC reproducen exactamente cada total nacional correspondiente. El diccionario identifica cada universo y fuente. Se conservan también los análisis individuales exploratorios anteriores como resultados complementarios, identificados por su unidad de análisis.

## Entregables y datos

| Entregable | Contenido | Forma de entrega |
|---|---|---|
| `Caso1_EH2025_Final_GitHub.zip` | Código, cuaderno, informe, EDA, visualizaciones, datos municipales agregados CSV/Parquet, fuentes y controles | Descomprimir y publicar su contenido en GitHub |
| `Caso1_EH2025_Dataset_Academico.zip` | Dataset individual EH2025 procesado y documentación de su preparación | Entrega académica separada con acceso controlado; no cargar al repositorio público |

El dataset municipal es agregado y público. El dataset individual procesado sigue siendo microdato aunque se retiren identificadores directos. El paquete académico separado satisface la entrega del dataset procesado sin confundirlo con el conjunto municipal. Los archivos originales SAV/DTA, los modelos serializados y las carpetas privadas no forman parte del paquete público.

## Estructura

```text
Proyecto_EH2025_ML_Caso1/
├── data/             # metadatos, fuentes municipales y cartografía
├── notebooks/        # cuaderno completo
├── src/              # preparación, encuesta, modelos, visualización e informe
├── outputs/
│   ├── descriptive/  # estimaciones y perfiles individuales agregados
│   ├── model_evaluation/
│   ├── figures/
│   └── municipal/    # dataset 343×47, perfiles, controles, mapa y PCA
├── docs/             # informe final, explorador y guía de entrega
├── checks/
├── tests/
├── requirements.txt
├── run.py
└── README.md
```

## Reproducir

Usar Python 3.12. En la raíz del proyecto, instalar las versiones definidas:

```bash
python -m pip install -r requirements.txt
```

El componente municipal puede regenerarse con las fuentes agregadas incluidas. Para repetir también la extracción desde los seis Excel oficiales, ejecutar antes:

```bash
python data/preparar_municipios_censo2024.py --data-dir data/municipal --geojson data/bolivia_municipios_2024.geojson
```

Después, generar datos procesados, perfiles y gráficos:

```bash
python run.py municipal
```

Para repetir el análisis individual, obtener los módulos Persona y Vivienda desde [ANDA/INE](https://anda.ine.gob.bo/index.php/catalog/256). La procedencia y fecha de descarga declaradas para los archivos recibidos son ANDA, **15 de noviembre de 2026**; su estructura se contrastó con los metadatos. Guardar copias como `data/raw/EH2025_Persona.sav` y `data/raw/EH2025_Vivienda_1.sav`. Si se usan otros archivos o DTA, registrar sus rutas, formato y fecha real en `data/source_manifest.json`.

Ejecutar en orden:

```bash
python run.py preflight
python run.py prepare
python run.py profile
python run.py model
python run.py visualize
python run.py municipal
python run.py deliver-dataset
python -m src.finalize
python -m src.build_report
```

`prepare` genera el conjunto individual local `outputs/private/analysis.parquet`. `deliver-dataset` prepara la entrega académica en `outputs/entrega_restringida/`; ambas carpetas están excluidas de Git. El dataset municipal público CSV/Parquet se genera en `outputs/municipal/`.

Los identificadores no se usan como predictores; se excluyen variables que reproducen la asistencia. La validación agrupa por UPM y estratifica el objetivo; las transformaciones se aprenden dentro del entrenamiento. Los resultados predictivos no son estimaciones causales.

`src.finalize` regenera el explorador; `src.build_report` regenera el Word. Para actualizar el PDF, exportar el Word final desde Word o LibreOffice y revisar el resultado, conservando el máximo de 15 páginas establecido en la consigna. La generación del Word no convierte automáticamente el PDF.

## Comprobaciones y trazabilidad

```bash
python checks/check_ingestion.py
python checks/check_modeling.py
python -m unittest discover -s tests -p 'test_survey.py' -v
```

Los controles de ingesta/modelos usan datos sintéticos aislados; los resultados analíticos incluidos se obtuvieron de los datos oficiales recibidos. El estimador se contrastó con ejemplos manuales y un control independiente. El cuaderno completo ejecutó sus 10 celdas de código, preservando los resultados numéricos previos de la EH2025. El control se registra en `outputs/notebook_execution_audit.json`. En macOS, `run.py` configura OpenMP para las etapas normales cuando la biblioteca del entorno lo requiere.

Las seis fuentes XLSX municipales, enlaces y hashes están en `data/municipal/`; el diccionario registra universos y columnas originales. El cruce geográfico conserva nombres INE/UDAPE y documenta 334 coincidencias exactas normalizadas más nueve equivalencias explícitas auditadas, con cobertura 343/343 y sin uniones difusas ni asignación de municipios a personas EH.

Fuentes: [INE, tabulados censales de educación](https://www.ine.gob.bo/index.php/censos-educacion/), [INE, indicadores censales](https://www.ine.gob.bo/index.php/estadisticas-economicas/censos-indicadores/) y [UDAPE, Atlas 2025](https://sigudape.udape.gob.bo/atlas2025/). Los indicadores municipales corresponden al Censo 2024; el año del atlas no cambia el año de esos indicadores. La cartografía es referencial y no define límites legales. El mapa departamental complementario utiliza geoBoundaries BOL ADM1, esquema representado 2015, con atribución CC BY 4.0 documentada en `data/metadata/cartography_source.json`.

El repositorio y el envío de Moodle deben realizarse siguiendo la guía incluida. La preparación local de estos archivos no acredita publicación ni entrega en la plataforma.
