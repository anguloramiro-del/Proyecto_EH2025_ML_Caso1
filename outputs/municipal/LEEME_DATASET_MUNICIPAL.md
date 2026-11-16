# Cómo leer este dataset municipal

Unidad: municipio o TIOC, Censo 2024; 343 filas. Este archivo es entrada real del agrupamiento territorial y conserva los indicadores originales. No contiene personas de EH2025. Consulte `diccionario_dataset_municipal_procesado.csv`, `municipal_summary.json` y el README del componente municipal.

Las variables con prefijo `z_` se calculan con media y desviación poblacional de las 343 jurisdicciones, con pesos iguales. `perfil_municipal` es descriptivo; `pca1` y `pca2` son coordenadas de visualización de las cuatro variables estandarizadas. Las medias de perfiles son medias entre municipios y se distinguen de tasas censales agrupadas calculadas con conteos.

No asistencia actual no demuestra abandono longitudinal. Los denominadores educativos y de servicios no son intercambiables. Fuente de agua mejorada no certifica potabilidad. Los perfiles no autorizan asignaciones de recursos ni decisiones sobre personas sin validación local.

Fuentes: INE Censo 2024 (educación y servicios); geometría de referencia UDAPE Atlas 2025. Acceso: 15/11/2026. Mantener la atribución y las notas de procedencia del proyecto.
