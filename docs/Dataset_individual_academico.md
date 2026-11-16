# Complemento académico restringido con dataset procesado EH2025

Este complemento contiene **datos reales procesados a nivel de persona**. Es una entrega de evaluación académica separada del repositorio público. No se ha subido ni enviado a ningún servicio o destinatario.

## Qué contiene

| Archivo | Unidad y contenido | Uso |
|---|---|---|
| outputs/dataset_analitico_eh2025_minimizado.csv y .parquet | 4.731 adolescentes; 10 predictores, objetivo y factor; 12 columnas | Revisión del dataset analítico y sus faltantes |
| outputs/dataset_analitico_eh2025_diseno_restringido.csv y .parquet | Las mismas 4.731 filas y valores; añade estrato y UPM anónima; 14 columnas | Reproducir validación agrupada por UPM y análisis ponderado |
| outputs/plan_muestral_upm_restringido.csv y .parquet | 1.088 parejas únicas estrato–UPM, incluidos 41 conglomerados sin adolescentes en la cohorte | Conservar la estructura de muestreo completa en la varianza de dominio |
| outputs/diccionario_dataset_analitico.json y .csv | Etiquetas oficiales, roles, unidades, categorías y notas de faltantes | Evitar interpretar códigos como magnitudes o incluir campos de diseño como predictores |
| outputs/auditoria_entrega_dataset.json | Conteos, controles de códigos, reproducción y huellas SHA-256 | Verificación de integridad sin mostrar filas |

No se incluyen folio, nro, nombres, domicilios ni identificadores nuevos. La UPM y el estrato anónimos de la fuente se conservan exclusivamente en la versión de diseño y el plan restringidos. No identifican el municipio actual y no deben intentarse reconstrucciones geográficas.

## Definición analítica

El universo propuesto son adolescentes de 12 a 17 años, con etiqueta conocida. La variable inasistencia vale 1 si cmasi original es 1 o 3 y 0 si es 2. Hay 169 casos positivos y 4.562 asistentes. El indicador es transversal y no mide abandono entre años. cmasi y las preguntas que reproducen el objetivo no se exportan como predictores.

Los datos están cruzados y filtrados, con códigos preservados. No se imputan globalmente antes de entregar: el ingreso per cápita conserva 1 faltante y desagüe sanitario 1.274. La imputación usada en los modelos se aprende dentro de cada entrenamiento. El patrón de desagüe es compatible con un salto del cuestionario y no equivale automáticamente a un error.

La versión Parquet conserva los tipos y es preferible para reproducir el cálculo exacto. El CSV está en UTF-8 con BOM, con 17 dígitos significativos para los números. Se comprobó su lectura con float_precision="round_trip" y tipos categóricos definidos en el diccionario. Abrir y volver a guardar el CSV desde una hoja de cálculo puede cambiar precisión o tipos; conservar las copias de entrega y comprobar sus huellas.

## Alcance de la reproducción

La tabla minimizada no contiene UPM y no permite reproducir por sí sola la partición agrupada. La versión de diseño sí mantiene los grupos originales y reproduce las particiones. Para estimar incertidumbre de la cohorte se requiere además el plan completo: usar solo las 1.047 UPM observadas en adolescentes omitiría 41 UPM fuera del dominio.

Se verificó, con la versión de diseño más el plan completo, tasa ponderada nacional 4,156855398686901% y error estándar ajustado 0,6712975396676907 puntos porcentuales, idénticos al cálculo sobre la base completa. La convención para los dos estratos con una UPM se conserva como adjust explícito, sin FPC; no es una estimación oficial. Las variables educativas auxiliares para auditorías de matrícula o sensibilidad por culminación permanecen en los originales y se regeneran mediante el pipeline; no se añaden a los predictores de este complemento.

## Regenerar

Desde la raíz del proyecto, con los módulos oficiales ya preparados:

```bash
python -m src.delivery_dataset --project-root . --output-dir outputs/entrega_restringida
```

El exportador no modifica las fuentes. Verifica filas, objetivo, edades, códigos, ponderadores, plan muestral, lectura de CSV/Parquet, particiones agrupadas y estimador de referencia. Si se cambia el universo o la versión de la encuesta, no debe saltarse silenciosamente la comprobación de 4.731 filas y 169 positivos: documentar y revisar el cambio de proyecto.

## Acceso y entrega

Conservar las condiciones y el protocolo de acceso que exige ANDA también para los datos procesados. Este complemento no forma parte del ZIP público de GitHub. Su preparación local no concede derechos adicionales sobre la información ni demuestra que un tercero ya tenga acceso autorizado.

Para evaluación, utilizar únicamente un mecanismo académico de acceso restringido compatible con esas condiciones. Cuando la actividad de Moodle permita adjuntos restringidos, el complemento puede acompañar al enlace del repositorio conforme a las reglas aplicables de acceso; si la actividad solo admite la URL, debe definirse con el docente un canal compatible para el dataset individual. No se ha realizado ninguna entrega desde este trabajo.

El repositorio público puede contener el exportador, las instrucciones de acceso y el **dataset municipal agregado que entra al clustering**, con su propia fuente y año. Esa tabla municipal es un dataset procesado diferente: no sustituir nombres ni mezclar municipios con personas EH2025. Las filas de este complemento no deben copiarse al repositorio público.

Condiciones de la fuente: https://anda.ine.gob.bo/index.php/catalog/256 (Condiciones de uso y Requerimientos de citación). El catálogo indica registro para la obtención y conservación de condiciones/protocolo de acceso en procesados. Los resultados e interpretaciones propios no tienen carácter oficial del INE.

Fuente: Instituto Nacional de Estadística, Encuesta de Hogares 2025 - http://anda.ine.gob.bo/index.php/catalog/256. Fecha de acceso: 15 de noviembre de 2026.
