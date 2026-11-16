# Acceso y trazabilidad

Fuente: Instituto Nacional de Estadística, Encuesta de Hogares 2025 - http://anda.ine.gob.bo/index.php/catalog/256. Fecha de acceso: 15 de noviembre de 2026.

El usuario confirmó descarga desde ANDA el 15/11/2026. Los siete SAV se contrastaron con el diccionario oficial. Para reproducir se requieren EH2025_Persona.sav y EH2025_Vivienda_1.sav, colocados en raw/ con esos nombres y declarados en source_manifest.json. Los originales no se redistribuyen. La conversión conserva códigos y etiquetas y produce Parquet local.

Los metadatos oficiales y la cartografía de referencia están en metadata/ y bolivia_departamentos.geojson. La descarga de la capa se reproduce con download_cartography.py; fuente y licencia CC BY 4.0 constan en cartography_source.json. El esquema geográfico es de 2015, no una cartografía INE 2025.
