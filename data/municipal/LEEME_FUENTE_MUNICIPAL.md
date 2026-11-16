# Fuente municipal complementaria: Censo2024 INE

Este conjunto es independiente de los microdatos EH2025. Cada fila es un municipio o TIOC del tabulado oficial del Censo2024. No contiene estudiantes individuales, no asigna personas EH a municipios y no produce tasas municipales EH2025.

## Procedencia y reproducción

- Educación INE: https://www.ine.gob.bo/index.php/censos-educacion/
- Indicadores censales INE: https://www.ine.gob.bo/index.php/estadisticas-economicas/censos-indicadores/
- Los seis enlaces directos de descarga, tamaños y SHA256 constan en `download_manifest.json`.
- Cartografía y códigos: Atlas UDAPE2025, capa oficial `atlas2025:pg_v_nbi_2024`. La fuente y el proceso cartográfico se documentan por separado. Los códigos se usan solo para unir agregados censales con su geometría.
- Extracción: Python 3.10 o superior y `openpyxl`. Para volver a descargar se requiere además `requests`.

Desde la raíz del proyecto:

```bash
python data/preparar_municipios_censo2024.py --data-dir data/municipal --geojson data/bolivia_municipios_2024.geojson
```

Añadir `--download` al final para descargar nuevamente las seis fuentes XLSX. Sin esa opción se usan las fuentes ya incluidas. El programa valida la cobertura de 343 municipios/TIOC, sus códigos únicos, los rangos porcentuales y los totales nacionales antes de escribir la salida. No utiliza coincidencia difusa.

## Archivos derivados de las fuentes

- `municipios_censo2024_indicadores.csv`: 343 filas y 38 columnas de indicadores y trazabilidad; los códigos de seis dígitos se conservan como texto.
- `diccionario_municipios_censo2024.csv`: definiciones, unidades, año, universo, archivo y columnas originales de cada variable.
- `equivalencias_municipios_ine_udape.csv`: 334 uniones exactas tras normalizar mayúsculas, acentos y espacios, más nueve equivalencias explícitas auditadas. Conserva los nombres INE y UDAPE originales. El TIOC TIM tiene provincia nula en UDAPE; no se imputa dicha provincia.
- `aliases_municipales_auditados.json`: las nueve excepciones de nombres o provincia, confirmadas con los atributos originales de la capa UDAPE.
- `validacion_municipios_censo2024.json`: controles, faltantes, cobertura y advertencias.

El conjunto final con transformaciones, componentes principales y grupos se genera después mediante `python run.py municipal`, en `outputs/municipal/`. No confundir las 38 columnas de esta extracción de fuentes con las 47 columnas del dataset municipal procesado final.

## Variables recomendadas para agrupamiento

- `no_asistencia_12_17_pct`: 100 menos la tasa de asistencia educativa censal de 12 a 17 años.
- `ruralidad_12_17_pct`: porcentaje rural del mismo denominador del indicador de asistencia de 12 a 17 años.
- `anios_estudio_19_mas`: años promedio de estudio de adultos de 19 años o más del municipio, como contexto agregado.
- `100 - agua_mejorada_12_17_pct`: carencia de acceso a una fuente mejorada de agua entre adolescentes en viviendas particulares. Una fuente mejorada no equivale necesariamente a agua potable certificada.

Las cuatro variables tienen cobertura de 343/343, sin valores imputados. La población de un área urbana o rural inexistente se representa por cero solamente cuando el otro componente suma exactamente la población total. Las tasas de asistencia de áreas sin población permanecen vacías: 158 municipios sin tasa urbana y uno sin tasa rural. Esos campos opcionales no se usan para agrupar.

## Universos y límites

Los cuadros de educación excluyen residentes habituales en el exterior y personas que no declararon en las preguntas correspondientes. Los cuadros de servicios corresponden a población en viviendas particulares con personas presentes.

Los denominadores no son intercambiables:

| Indicador | Denominador nacional 2024 |
|---|---:|
| Asistencia educativa, 12–17 años |1.265.155|
| Escolaridad de al menos seis años, población de 12–17 años |1.270.984|
| Servicios, población de 12–17 años en viviendas particulares |1.272.725|
| Promedio de estudio, población de 19 años o más |7.350.282|
| Servicios, población total en viviendas particulares |11.134.130|

Las sumas de los 343 municipios/TIOC reproducen exactamente cada total nacional del cuadro correspondiente. Se reconstruyeron 84.649 adolescentes que no asisten en el universo válido del indicador, equivalentes a 6,6908007319%; la asistencia nacional es 93,3091992681%. El número se verifica como entero a partir del porcentaje sin redondear y la población del cuadro.

La no asistencia observada no demuestra abandono longitudinal ni anticipa individualmente un abandono futuro. Los grupos municipales son perfiles contextuales descriptivos: las asociaciones agregadas no prueban causalidad ni caracterizan a todas las personas de un municipio. Tampoco se comparan como si fueran idénticos a resultados EH2025, que tienen otro año, universo y diseño.

La cartografía es una referencia geoestadística para visualización; no define límites legales. La unidad publicada por INE es municipio/TIOC y se debe denominar así en mapas e informes.
