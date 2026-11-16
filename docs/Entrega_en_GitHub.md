# Paso a paso: publicar el proyecto y entregar el enlace en Moodle

Esta guía corresponde a la versión final: incluye el componente municipal real de 343 municipios/TIOC del Censo 2024 y dos entregas de datos diferenciadas. La publicación y el envío a Moodle todavía deben realizarse desde la cuenta del estudiante.

## 1. Identificar los dos paquetes

En Finder, ubicar los archivos finales y conservarlos separados:

| Archivo | Para qué sirve | Destino |
|---|---|---|
| `Caso1_EH2025_Final_GitHub.zip` | Proyecto público: informe, código, cuaderno, EDA, figuras y dataset municipal agregado | GitHub, después de descomprimir |
| `Caso1_EH2025_Dataset_Academico.zip` | Dataset individual EH2025 procesado y sus documentos de apoyo | Entrega académica con acceso controlado |

El segundo archivo **no se carga al repositorio público**. El dataset municipal agregado ya está dentro del primer paquete, en CSV y Parquet; no reemplaza el dataset individual requerido por la tarea.

1. Hacer doble clic en `Caso1_EH2025_Final_GitHub.zip` para descomprimirlo.
2. Abrir la carpeta `Proyecto_EH2025_ML_Caso1` que contiene `README.md`, `run.py` y las carpetas `data`, `docs`, `notebooks`, `src` y `outputs`.
3. Abrir `docs/Informe_Caso1_EH2025_Final.pdf`. Revisar el título, resultados, propuesta de políticas, componente municipal y referencias. El Word editable está junto al PDF.
4. Abrir `docs/Explorar_resultados.html` con el navegador. Recorrer el mapa municipal, PCA y las demás visualizaciones.
5. Comprobar que `outputs/municipal/` contiene `dataset_municipal_procesado_2024.csv` y `dataset_municipal_procesado_2024.parquet`.

Conservar la estructura de carpetas. Para explorar los HTML es necesario descargar el proyecto completo; la vista habitual de GitHub muestra su código.

## 2. Crear el repositorio

1. Entrar en [GitHub](https://github.com/) e iniciar sesión en la cuenta propia.
2. Abrir [Nuevo repositorio](https://github.com/new).
3. En **Owner**, seleccionar la cuenta propia.
4. En **Repository name**, escribir `Proyecto_EH2025_ML_Caso1`.
5. En **Description**, se puede escribir: `Caso 1: no asistencia educativa, EH2025 y perfiles municipales Censo 2024 con DuckDB, ML y visualización interactiva.`
6. Seleccionar **Public** si la consigna exige un enlace público.
7. Dejar desactivadas las opciones para crear README, `.gitignore` y licencia iniciales: el paquete ya contiene sus documentos y reglas.
8. Hacer clic en **Create repository**.

La secuencia y las opciones se basan en la [documentación oficial para crear un repositorio](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository).

## 3. Subir el contenido en dos tandas

GitHub admite hasta 100 archivos por carga web y 25 MiB por archivo. Cuando el proyecto supera 100 archivos, usar las dos tandas siguientes para conservar sus carpetas. No arrastrar el ZIP ni la carpeta exterior `Proyecto_EH2025_ML_Caso1`: subir **su contenido**. Los límites y la carga de carpetas constan en la [documentación oficial de GitHub](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

### Primera tanda: documentación, código y fuentes (60 archivos)

1. En la página principal del repositorio, elegir **Add file → Upload files**. Si está vacío, puede aparecer directamente un enlace para cargar archivos.
2. En Finder, entrar en la carpeta descomprimida `Proyecto_EH2025_ML_Caso1`.
3. Seleccionar estos archivos y carpetas, manteniendo presionada la tecla **Command** para seleccionar varios:
   - `README.md`, `run.py`, `config.json`, `requirements.txt` y `MANIFEST_SHA256.json`.
   - `.gitignore`.
   - Las carpetas completas `data`, `docs`, `notebooks`, `src`, `checks` y `tests`.
4. Si `.gitignore` no aparece, presionar **Command + Shift + punto** en Finder para mostrar los archivos ocultos. Volver a la misma combinación al terminar si se desea ocultarlos.
5. Arrastrar la selección al área de carga de GitHub. No incluir `outputs` en esta primera tanda.
6. Esperar hasta que todos los archivos seleccionados terminen de cargar. Revisar la lista: deben conservar rutas como `docs/Informe_Caso1_EH2025_Final.pdf` y `src/...`.
7. En el mensaje de cambios, escribir: `Agregar informe final, código, cuaderno y fuentes oficiales`.
8. Confirmar con **Commit changes** o **Propose changes**, según la pantalla.
9. Si GitHub crea una rama y una solicitud de cambios, abrirla, crear la solicitud si se pide y completar **Merge pull request → Confirm merge**. Comprobar que los archivos queden en la rama principal antes de continuar.

### Segunda tanda: resultados (67 archivos)

1. Volver a la página principal del repositorio.
2. Elegir nuevamente **Add file → Upload files**.
3. Desde Finder, arrastrar únicamente la carpeta completa `outputs` al área de carga.
4. Comprobar que las rutas comienzan por `outputs/`, por ejemplo `outputs/municipal/dataset_municipal_procesado_2024.csv`.
5. Esperar hasta terminar la carga.
6. Escribir como mensaje: `Agregar EDA, evaluaciones, visualizaciones y dataset municipal procesado`.
7. Confirmar los cambios e integrar la solicitud si GitHub usa una rama nueva.

Las carpetas vacías no se muestran en GitHub. Si una tanda excediera el límite, dividirla en grupos adicionales de menos de 100 archivos conservando las rutas; no omitir resultados. La carga web no aplica automáticamente `.gitignore`: usar exclusivamente el paquete público preparado y mantener fuera el ZIP académico y las carpetas locales `outputs/private` y `outputs/entrega_restringida`.

## 4. Revisar lo que quedó publicado

En la página principal del repositorio, verificar:

- Se muestra el README con el título final del proyecto.
- Existen `data/`, `docs/`, `notebooks/`, `src/`, `outputs/`, `checks/` y `tests/` directamente en la raíz.
- El PDF final se abre desde `docs/Informe_Caso1_EH2025_Final.pdf`.
- El cuaderno `notebooks/03_Caso1_Completo.ipynb` está presente.
- En `outputs/municipal/` aparecen el CSV y el Parquet municipales, el mapa, PCA y perfiles.
- El EDA `outputs/eda_report.html` está presente.
- El repositorio público no contiene el paquete individual académico ni archivos SAV/DTA.

Abrir **Code → Download ZIP**, descomprimir esa descarga en otra carpeta y abrir allí el explorador HTML. Así se comprueba que la copia publicada conserva los resultados y sus enlaces. Para verificar acceso público, abrir el enlace del repositorio en una ventana privada sin iniciar sesión.

Si se observa una carpeta exterior adicional, por ejemplo `Proyecto_EH2025_ML_Caso1/Proyecto_EH2025_ML_Caso1/docs`, la estructura está anidada: subir los archivos desde dentro de la carpeta correcta para que README y las carpetas principales queden en la raíz.

## 5. Preparar el dataset académico separado

1. Conservar `Caso1_EH2025_Dataset_Academico.zip` fuera de la carpeta que se subirá a GitHub.
2. Abrir el ZIP y revisar que incluya los datos procesados y su documentación. No sustituirlo por los microdatos originales ni por una tabla vacía.
3. Entregar este ZIP por el espacio privado de archivos de la actividad, si Moodle lo ofrece. Si la actividad acepta solo un enlace, usar para el dataset el mecanismo privado que establezca el docente y restringir el acceso al evaluador.
4. Mantener el enlace público de GitHub como entrega del proyecto. El acceso controlado al dataset individual es una entrega separada y debe quedar identificada para el docente.

Para regenerar el paquete académico desde una instalación local con los microdatos, ejecutar en la raíz del proyecto:

```bash
python run.py deliver-dataset
```

La salida se prepara en `outputs/entrega_restringida/`, excluida de Git. Para repetir toda la preparación o el análisis, seguir la secuencia del README.

## 6. Entregar el enlace en Moodle

1. Abrir el repositorio en GitHub y situarse en su página principal, no dentro de un archivo.
2. Copiar la dirección de la barra del navegador. Debe tener la forma `https://github.com/USUARIO/Proyecto_EH2025_ML_Caso1`; reemplazar `USUARIO` por la cuenta real, sin entregar este ejemplo.
3. Entrar en Moodle, abrir el curso y localizar la actividad **Tarea Análisis Avanzado de Microdatos**.
4. Elegir la opción para agregar o editar la entrega. Su nombre puede variar según la configuración del curso.
5. Pegar el enlace del repositorio en el campo de texto o URL habilitado. Se puede acompañar de esta descripción:

   > Caso 1: no asistencia educativa en adolescentes de 12–17 años. El repositorio incluye informe final, cuaderno, DuckDB, EDA automatizado, Random Forest/XGBoost, visualizaciones y dataset municipal agregado de 343 municipios/TIOC del Censo 2024. El dataset individual EH2025 procesado se entrega por separado con acceso controlado.

6. Si la actividad permite archivos privados, adjuntar el ZIP académico en ese apartado.
7. Guardar los cambios. Si aparece un botón adicional para confirmar o enviar definitivamente la tarea, completar ese paso y la declaración académica que presente la plataforma.
8. Revisar que Moodle muestre el estado de entrega y la fecha correspondiente; conservar una captura o comprobante personal.

## Cómo describir correctamente el alcance

El requisito municipal se resolvió con agregados oficiales del Censo 2024 y cartografía UDAPE, como fuente complementaria. La EH2025 conserva el análisis individual y las estimaciones de encuesta. Los años 2024 y 2025 no se interpretan como una serie de cambios anuales ni la no asistencia como abandono longitudinal. El modelo supervisado tiene recall 0 al umbral 0,5 en la reserva y requiere validación adicional; no se presenta como sistema operativo de alertas.

Fuentes de esta guía: documentación oficial de GitHub consultada el 15/11/2026 y estructura del proyecto final. La preparación local del paquete no equivale a haber publicado el repositorio ni enviado la tarea a Moodle.
