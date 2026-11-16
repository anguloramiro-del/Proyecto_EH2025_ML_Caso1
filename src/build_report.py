"""Informe editable desde resultados agregados ya calculados.

Ejecutar con python -m src.build_report. La exportación PDF puede realizarse con
LibreOffice o Word; el informe final exportado se entrega en docs/.
"""
from pathlib import Path
import csv
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SOURCE='Fuente: Instituto Nacional de Estadística, Encuesta de Hogares 2025 - http://anda.ine.gob.bo/index.php/catalog/256. Fecha de acceso: 15 de noviembre de 2026.'
def read_json(path): return json.loads((ROOT/path).read_text())
def rates(name):
    with (ROOT/'outputs/descriptive'/f'tasas_{name}.csv').open() as f:return list(csv.DictReader(f))
def number(v, digits=2):
    if v is None or v=='':return 'No estimable'
    return f'{float(v):,.{digits}f}'.replace(',','@').replace('.',',').replace('@','.')
def integer(v):return number(v,0)
def interval(r):return number(r['ic95_adjusted_inf_pct'])+' a '+number(r['ic95_adjusted_sup_pct'])
def clean(text):return str(text).replace('\u2013','-').replace('\u2014','-').replace('–','-').replace('—','-')

def build_report(root=ROOT):
    global ROOT
    ROOT=Path(root)
    survey=read_json('outputs/descriptive/survey_summary.json');nat=survey['national']
    cluster=read_json('outputs/municipal/municipal_summary.json')
    metrics=read_json('outputs/model_evaluation/model_metrics.json')
    sens=read_json('outputs/sensitivity.json')
    with (ROOT/'outputs/municipal/perfiles_municipales.csv').open() as f:profiles=list(csv.DictReader(f))
    doc=Document();sec=doc.sections[0]
    sec.page_width=Inches(8.5);sec.page_height=Inches(11)
    sec.top_margin=sec.bottom_margin=Inches(.8);sec.left_margin=sec.right_margin=Inches(1)
    sec.header_distance=sec.footer_distance=Inches(.35)
    for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Caption','List Bullet','List Number']:
        st=doc.styles[name];st.font.name='Arial';st.font.color.rgb=RGBColor(0,0,0)
        st.paragraph_format.space_after=Pt(6)
    st=doc.styles['Normal'];st.font.size=Pt(11);st.paragraph_format.line_spacing=1.06
    doc.styles['Title'].font.size=Pt(22);doc.styles['Title'].font.bold=True
    doc.styles['Subtitle'].font.size=Pt(13)
    doc.styles['Heading 1'].font.size=Pt(16)
    doc.styles['Heading 1'].paragraph_format.space_before=Pt(3)
    doc.styles['Heading 2'].font.size=Pt(12)
    doc.styles['Caption'].font.size=Pt(9.5)
    doc.core_properties.author='Ramiro';doc.core_properties.title='No asistencia educativa en Bolivia'
    doc.core_properties.subject='Caso 1 EH2025 y complemento municipal del Censo 2024'
    hp=sec.header.paragraphs[0];hp.text='Caso 1   No asistencia educativa   EH2025 y Censo 2024';hp.runs[0].font.size=Pt(8.5)
    fp=sec.footer.paragraphs[0];fp.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    fp.add_run('Elaboración propia con fuentes INE y UDAPE   |   ').font.size=Pt(8)
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');fp._p.append(field)
    def p(text,style=None):return doc.add_paragraph(clean(text),style)
    def h(text):doc.add_heading(clean(text),level=1)
    def sub(text):doc.add_heading(clean(text),level=2)
    def page(title):doc.add_page_break();h(title)
    def table(headers,rows,widths):
        assert sum(widths)==9360
        t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
        pr=t._tbl.tblPr
        for tag in ['tblW','tblLayout','tblInd']:
            old=pr.find(qn('w:'+tag))
            if old is not None:pr.remove(old)
        tw=OxmlElement('w:tblW');tw.set(qn('w:w'),'9360');tw.set(qn('w:type'),'dxa');pr.append(tw)
        lay=OxmlElement('w:tblLayout');lay.set(qn('w:type'),'fixed');pr.append(lay)
        ind=OxmlElement('w:tblInd');ind.set(qn('w:w'),'0');ind.set(qn('w:type'),'dxa');pr.append(ind)
        grid=t._tbl.tblGrid
        for el in list(grid):grid.remove(el)
        for w in widths:
            el=OxmlElement('w:gridCol');el.set(qn('w:w'),str(w));grid.append(el)
        borders=OxmlElement('w:tblBorders')
        for side in ['top','left','bottom','right','insideH','insideV']:
            el=OxmlElement('w:'+side);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
        pr.append(borders)
        for ri,values in enumerate([headers]+rows):
            row=t.rows[0] if ri==0 else t.add_row()
            trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
            if ri==0:
                repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
            for ci,(c,value,w) in enumerate(zip(row.cells,values,widths)):
                c.width=Inches(w/1440);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                tcpr=c._tc.get_or_add_tcPr();tcw=tcpr.find(qn('w:tcW'));tcw.set(qn('w:w'),str(w));tcw.set(qn('w:type'),'dxa')
                marg=OxmlElement('w:tcMar')
                for side,val in [('top',70),('bottom',70),('left',85),('right',85)]:
                    el=OxmlElement('w:'+side);el.set(qn('w:w'),str(val));el.set(qn('w:type'),'dxa');marg.append(el)
                tcpr.append(marg)
                if ri==0:
                    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E5EEF3');tcpr.append(shade)
                c.text=clean(value)
                for cp in c.paragraphs:
                    cp.paragraph_format.space_after=Pt(0);cp.paragraph_format.line_spacing=1.03
                    cp.alignment=WD_ALIGN_PARAGRAPH.LEFT if (ci==0 or headers[1] in ['Variables verificadas','Evidencia en el proyecto','Decisión propuesta','Producto y verificación','Unidad y contenido']) else WD_ALIGN_PARAGRAPH.CENTER
                    for run in cp.runs:run.font.size=Pt(9.5);run.bold=ri==0
        after=p('');after.paragraph_format.space_after=Pt(1);after.paragraph_format.space_before=Pt(0)
        return t
    def fig(relative,caption,width=6.35,max_height=4.3):
        path=ROOT/relative
        with Image.open(path) as im:w,h0=im.size
        width=min(width,max_height*w/h0)
        para=p('');para.alignment=WD_ALIGN_PARAGRAPH.CENTER;para.paragraph_format.keep_with_next=True
        run=para.add_run();shape=run.add_picture(str(path),width=Inches(width))
        shape._inline.docPr.set('descr',clean(caption))
        cp=p(caption,'Caption');cp.paragraph_format.space_after=Pt(7)
    def small(text):
        q=p(text)
        for run in q.runs:run.font.size=Pt(9.5)
        return q
    doc.add_paragraph('No asistencia educativa en Bolivia','Title')
    doc.add_paragraph('Caso 1 EH2025 y complemento municipal del Censo 2024','Subtitle')
    p('Unidad 2 Minería de datos visuales\nAutor Ramiro\n15 de noviembre de 2026')
    h('Problema social y decisión propuesta')
    p('El problema social abordado es la discontinuidad de la formación de adolescentes no matriculados o que no asisten. El producto de política pública es una propuesta de piloto de continuidad y revinculación educativa, con diagnóstico por edad y perfiles municipales. La EH2025 orienta su diseño; la atención individual requiere registros educativos actuales.')
    p(f'En adolescentes de 12 a 17 años, la no asistencia educativa estimada es {number(nat["tasa_pct"])} %. El intervalo aproximado del 95 % va de {interval(nat)} %, con un ajuste explícito para dos estratos con una sola unidad primaria de muestreo (UPM). La brecha descriptiva es mayor en el área rural y en las edades de 16 a 17 años; la precisión de varias desagregaciones limita su uso para asignar recursos.')
    p('XGBoost supera a Random Forest en la métrica de selección, pero ninguno detecta casos positivos en la reserva con el umbral predefinido de 0,5. El resultado permite estudiar patrones y orientar un piloto de acompañamiento; todavía no respalda un sistema automático de alertas.')
    table(['Condición en la muestra de 12 a 17 años','Adolescentes'],[['Asiste','4.562'],['No matriculado','161'],['Matriculado que no asiste','8'],['Total analizado','4.731']],[7200,2160])
    p('La encuesta es transversal. El indicador analizado agrupa no matrícula y no asistencia; no mide abandono entre años ni identifica causas. Se conservan esta distinción y la sensibilidad por culminación de estudios en toda interpretación.')
    sub('Dos fuentes y dos niveles de análisis')
    p('Los modelos individuales se estiman con la EH2025. El agrupamiento municipal utiliza tabulados públicos del Censo 2024 y códigos de la cartografía UDAPE, con 343 municipios/TIOC. El componente municipal queda desarrollado con una fuente complementaria identificada, sin asignar municipios a personas EH ni interpretar las diferencias entre fuentes como cambios anuales. La no asistencia es el indicador observable; no se reconstruye abandono longitudinal.')
    small(SOURCE)

    page('Datos y preparación del análisis')
    p('Los siete archivos SPSS recibidos coinciden con los conteos y nombres de variables del diccionario BOL-INE-EH-2025. Persona contiene 39.485 registros y 276 variables; Vivienda, 12.726 registros y 64 variables. Los originales se conservaron y se verificaron las huellas de sus copias. Los módulos de educación, salud y empleo están integrados en Persona.')
    p('La lectura preserva códigos y etiquetas por separado y convierte únicamente los faltantes declarados a valores nulos. Se convierte SAV a Parquet y se realiza un cruce DuckDB de muchos a uno por folio. La clave de persona es folio y nro. No hay claves nulas, duplicadas ni personas sin hogar asociado; las 39.485 filas y la suma de factores se mantienen. Este volumen no requirió Dask.')
    table(['Papel','Variables verificadas'],[['Objetivo','cmasi 1 o 3 → no asistencia; cmasi 2 → asiste'],['Universo','Edad s01a_03 de 12 a 17 años inclusive'],['Numéricas','Edad, ingreso per cápita del hogar y número de personas del hogar'],['Categóricas','Sexo, departamento, área, fuente de agua, tipo de sanitario, desagüe y electricidad'],['Diseño y enlace','factor, estrato, upm, folio y nro; no son predictores'],['Excluidas por fuga','Matrícula, razones de inasistencia, cmasi como predictor y variables que reproducen el objetivo']],[2400,6960])
    sub('Calidad de los datos y EDA automatizado')
    p('En el universo hay cero objetivos faltantes y un ingreso per cápita faltante. La variable de desagüe tiene 1.274 faltantes, todos en tipos sanitarios distintos del baño con descarga de agua. El patrón es compatible con un salto del cuestionario; se conserva como categoría faltante para el modelo y no se transforma en cero. Esta codificación puede actuar como señal del flujo del formulario y debe revisarse con la pregunta original.')
    p('El reporte YData-Profiling se entrega en outputs/eda_report.html con 10 predictores y el objetivo, sin identificadores ni muestras de filas. Es un EDA de la muestra sin ponderar; las estimaciones poblacionales se calculan aparte. El ingreso se imputa dentro del entrenamiento de cada partición.')

    sub('Cómo el stack tecnológico sustenta la decisión pública')
    p('DuckDB asegura que el cruce no duplique personas ni ponderadores. El EDA automatizado detecta faltantes y posibles saltos del cuestionario que modificarían la interpretación. Machine Learning compara señales predictivas y revela que aún no existe un detector operativo validado. Las visualizaciones muestran diferencias por edad, contexto y territorio junto con su incertidumbre. El aporte conjunto es una priorización razonada para diseñar y evaluar un piloto, sin convertir asociaciones en causas ni colores del mapa en asignaciones presupuestarias.')

    page('Magnitud de la no asistencia y precisión')
    p('Se estima una razón ponderada: suma de factores de los adolescentes con no asistencia dividida entre la suma de factores de todos los adolescentes del universo. Los recuentos muestrales y los porcentajes ponderados responden a cantidades distintas y se presentan por separado.')
    display=[['Nacional',integer(nat['n_muestra']),number(nat['tasa_pct']),interval(nat),number(nat['cv_adjusted_pct'])]]
    for group,col in [('area','area'),('sexo','sexo')]:
        for r in rates(group):display.append([r[col],integer(r['n_muestra']),number(r['tasa_pct']),interval(r),number(r['cv_adjusted_pct'])])
    table(['Dominio','n','Tasa %','IC 95 % aprox.','CV %'],display,[2520,1080,1440,2880,1440])
    fig('outputs/figures/02_area_sexo_ic.png','Figura 1 No asistencia por área y sexo con IC aproximados. Fuente INE EH2025 y elaboración propia.',max_height=3.3)
    small('Los IC usan linealización Taylor sobre la muestra completa, con contribución cero fuera del dominio, estratos y UPM. Los estratos 322 y 821 tienen una UPM: la varianza estricta no es estimable. Se aplica y etiqueta la convención adjust centrada globalmente, sin corrección por población finita. El ajuste aporta 1,89 % de la varianza nacional. No son intervalos oficiales del INE.')
    small('El CV nacional aproximado es 16,15 %. CV mayor de 20 % identifica estimaciones sujetas a evaluación, no una prueba de hipótesis. La precisión prevista para pobreza no se traslada automáticamente a este subgrupo educativo.')

    page('Patrones geográficos y límites del mapa')
    fig('outputs/figures/01_mapa_no_asistencia.png','Figura 2 Tasas por dominio geográfico. El tramado señala CV superior a 20 %. Beni y Pando comparten una sola estimación.',max_height=3.65)
    table(['Dominio','n','Tasa %','IC 95 % aprox.','CV %'],[[r['region'],integer(r['n_muestra']),number(r['tasa_pct']),interval(r),number(r['cv_adjusted_pct'])] for r in rates('region')],[2520,1080,1440,2880,1440])
    p('Todos los dominios regionales tienen CV aproximado superior a 20 %. Las diferencias de color son descriptivas; no permiten establecer un orden firme de riesgo ni justificar una asignación municipal de recursos. No se realizaron pruebas de diferencias entre departamentos.')
    small('Cartografía referencial geoBoundaries BOL ADM1, esquema representado de 2015, distribución CC BY 4.0; origen GeoBolivia Public Domain según la API. No es cartografía INE de 2025 ni fuente de los indicadores. Las tasas proceden exclusivamente de los microdatos EH2025.')

    page('Edad y definición del resultado educativo')
    table(['Edad','n','No asistencia %','IC 95 % aprox.','CV %'],[[r['tramo_edad'],integer(r['n_muestra']),number(r['tasa_pct']),interval(r),number(r['cv_adjusted_pct'])] for r in rates('tramo_edad')],[1800,1080,1800,3240,1440])
    fig('outputs/figures/03_edad_area_ic.png','Figura 3 No asistencia por edad y área. Barras e intervalos son estimaciones descriptivas con el ajuste declarado.',max_height=3.65)
    p('La estimación aumenta desde 1,29 % a los 12 y 13 años hasta 7,39 % a los 16 y 17. El último tramo reúne 97 de los 169 casos muestrales de no asistencia y tiene CV aproximado de 14,50 %. Estos patrones justifican estudiar la continuidad educativa al final de la adolescencia, sin atribuir el cambio a la edad como causa.')
    sub('Sensibilidad por culminación de estudios')
    p(f'Hay 13 adolescentes con secundaria completa o estudios superiores; 11 pertenecen al objetivo positivo. Al excluirlos, el universo pasa a {integer(sens["restricted_n"])} casos y la tasa ponderada baja de {number(100*sens["full_rate_weighted"])} % a {number(100*sens["restricted_rate_weighted"])} %. Es una sensibilidad descriptiva: no se reentrenaron ni seleccionaron modelos con esta exclusión. Antes de cualquier contacto se debe verificar si la trayectoria ya concluyó.')

    page('Perfiles municipales de vulnerabilidad educativa')
    p(f'El componente municipal utiliza 343 municipios/TIOC del Censo 2024. El cruce con códigos UDAPE conserva 334 coincidencias normalizadas y nueve equivalencias explícitas verificadas. No hay unidades sin correspondencia ni estimaciones municipales derivadas de la EH. Cada jurisdicción tiene igual peso en el agrupamiento.')
    p(f'K-Means sobre cuatro indicadores estandarizados selecciona k={cluster["selected_k"]}: no asistencia de 12 a 17 años, ruralidad del mismo universo, años de estudio de la población de 19 o más años y carencia de fuente mejorada de agua entre adolescentes en viviendas particulares. No hay faltantes ni imputación. La silhouette es {number(cluster["silhouette"],3)}; k=5 obtiene un valor casi igual, por lo que no se afirma una partición única óptima.')
    fig('outputs/municipal/pca_municipal_2024.png','Figura 4 Proyección municipal del Censo 2024 y centroides de los perfiles. Cada punto representa una jurisdicción pública agregada.',max_height=3.1)
    table(['Perfil','Municipios TIOC','No asistencia media %','Ruralidad media %','Estudio adulto años','Sin agua mejorada %'],[[r['perfil'],integer(r['n_municipios']),number(r['no_asistencia_media_municipal_pct']),number(r['ruralidad_media_pct']),number(r['anios_estudio_media'],1),number(r['sin_agua_mejorada_media_pct'])] for r in profiles],[1260,1380,1800,1680,1560,1680])
    p('El perfil 4 reúne 63 jurisdicciones con mayor media municipal de no asistencia, 18,71 %, alta ruralidad y menor escolaridad adulta. El perfil 3 presenta la mayor carencia de fuente mejorada de agua, 48,47 %. Son tipologías descriptivas construidas usando la propia no asistencia; no prueban causas ni validan predicción futura.')
    small('Las cifras de perfiles son medias no ponderadas de municipios, no tasas de personas. Los universos difieren: educación excluye residentes habituales en el exterior y respuestas no declaradas; servicios corresponde a viviendas particulares con personas presentes. Agua mejorada no equivale a agua potable certificada. Fuente INE Censo 2024; procesamiento propio.')

    page('Mapa municipal con información complementaria')
    fig('outputs/municipal/mapa_municipal_2024.png','Figura 5 Mapa de los perfiles de 343 municipios/TIOC. La versión HTML permite alternar tasa de no asistencia 2024 y perfil municipal.',max_height=4.6)
    p('La capa municipal permite focalizar una verificación territorial sin reconstruir la ubicación de las personas EH2025. El mapa interactivo incorpora código, departamento, municipio/TIOC, población del universo, tasa y perfil. Las tablas oficiales suman 1.265.155 adolescentes con información válida de asistencia; 84.649 no asisten, equivalente a 6,69 %.')
    p('La cifra censal de 2024 y la estimación EH2025 de 4,16 % no conforman una serie anual comparable: cambian fuente, momento, definición operativa y denominadores. El mapa municipal describe el Censo 2024 y el mapa departamental anterior describe la EH2025. No se traslada una tasa departamental a sus municipios.')
    small('Referencia geográfica: UDAPE Atlas 2025, capa municipal/TIOC basada en información INE; WGS84. La simplificación de 0,0005 grados conserva geometrías válidas, pero no representa deslindes ni garantiza coincidencia exacta de bordes. Uso visual, sin cálculos de área ni asignación de personas. Acceso público verificado; no se atribuye una licencia abierta no identificada. Fuentes y huellas en data/municipal/.')

    page('Modelos supervisados y evaluación')
    p('Se comparan Random Forest de 200 árboles, mínimo de tres casos por hoja y max_features sqrt, y XGBoost de 200 árboles, profundidad 3, tasa de aprendizaje 0,05 y submuestras de filas y columnas de 0,8. Se fijan semilla 2026 y umbral 0,5. No se realiza búsqueda de hiperparámetros sobre la prueba.')
    p('StratifiedGroupKFold reserva el primer bloque de cinco para prueba: 945 adolescentes de 204 UPM, con 34 positivos. En 3.786 casos de 843 UPM se realiza validación interna de cinco particiones, estratificada por el objetivo y agrupada por UPM. No se comparte UPM entre entrenamiento y evaluación. Imputación y one-hot se ajustan dentro de cada entrenamiento; los factores se normalizan por su media para ajustar los modelos.')
    comparison=[]
    for key,label in [('random_forest','Random Forest'),('xgboost','XGBoost')]:
        m=metrics['models'][key];w=m['holdout']['weighted']
        comparison.append([label,number(m['cv_out_of_fold']['weighted']['average_precision'],4),number(w['roc_auc'],4),number(w['average_precision'],4),number(w['recall'],2),number(w['f1'],2)])
    b=metrics['baseline']['holdout']['weighted'];comparison.append(['Constante','No aplica',number(b['roc_auc'],4),number(b['average_precision'],4),number(b['recall'],2),number(b['f1'],2)])
    table(['Modelo','AP CV','AUC prueba','AP prueba','Recall','F1'],comparison,[2400,1440,1560,1440,1260,1260])
    small('AP es precisión promedio y resume la curva precisión recall; AUC es el área bajo la curva ROC. Métricas ponderadas. AP CV corresponde a predicciones fuera de fold, no al promedio simple de cinco AP. Precisión y recall de ambos modelos son cero a 0,5. La referencia usa probabilidad constante igual a la prevalencia ponderada de entrenamiento.')
    fig('outputs/model_evaluation/figures/roc_precision_recall.png','Figura 6 Curvas agregadas ROC y precisión recall de la reserva. AP y AUC se calculan con los scores originales antes de agregar la visualización.',max_height=3.0)
    p('XGBoost se elige por AP ponderada de validación 0,1727 frente a 0,1555 de Random Forest, antes de consultar la reserva. En prueba alcanza AP 0,1096 frente a la referencia 0,0327. Esta mejora de ordenamiento no demuestra capacidad operativa con el umbral fijado.')

    page('Errores de clasificación en la reserva')
    fig('outputs/model_evaluation/figures/confusion_matrices.png','Figura 7 Matrices de confusión observada y ponderada. Las sumas de pesos corresponden a la reserva y no al total nacional.',max_height=6.55)
    p('Random Forest clasifica como asistentes a los 945 casos: 911 verdaderos negativos y 34 falsos negativos. XGBoost añade un falso positivo, mantiene 910 verdaderos negativos y tampoco detecta los 34 positivos. La sensibilidad y F1 son cero en ambos casos.')
    p('Una exactitud ponderada cercana a 96,7 % es compatible con este fallo porque la no asistencia es minoritaria. El sistema no debe activarse con el umbral 0,5. Cualquier cambio de umbral requiere selección dentro de entrenamiento y validación y confirmación en una nueva reserva independiente.')

    page('Interpretación de las variables predictivas')
    fig('outputs/model_evaluation/figures/feature_importances.png','Figura 8 Importancias nativas agregadas por variable de origen. Las definiciones de cada modelo son diferentes.',max_height=3.2)
    p('En Random Forest el ingreso per cápita presenta la mayor importancia nativa agregada, 0,208, seguido del departamento, 0,125, y la edad, 0,115. En XGBoost destacan departamento, 0,220; fuente de agua, 0,150; área, 0,145; y desagüe sanitario, 0,140. Las señales apuntan a heterogeneidad de contexto y condiciones del hogar; la importancia no informa si cada categoría eleva o reduce la no asistencia.')
    p('Random Forest utiliza reducción normalizada de impureza y puede favorecer variables continuas o con más categorías. XGBoost usa gain por variable transformada. Al sumar indicadores one-hot, la cardinalidad y la correlación entre variables afectan los resultados. Los valores de los dos modelos no son una escala sustantiva común y no deben interpretarse como porcentajes causales.')
    sub('Implicación para la toma de decisiones')
    p('El desacuerdo entre modelos sobre la relevancia del ingreso impide reducir la explicación a una sola carencia. Las condiciones sanitarias también reflejan el flujo del cuestionario. Las variables sirven para formular hipótesis y diseñar una evaluación de barreras educativas; no demuestran que una intervención sobre agua o ingreso produzca un efecto determinado.')
    p('La reserva contiene solo 34 positivos. No se calcularon intervalos de incertidumbre predictiva ni significación de la diferencia de AUC. La validación separa UPM de la misma encuesta, no periodos futuros ni una población externa.')

    page('Tres recomendaciones sustentadas en los resultados')
    sub('1 Seguimiento de continuidad educativa a los 16 y 17 años')
    p('Proponer un piloto de contacto y orientación al final de secundaria, con verificación de matrícula, culminación y motivo de no asistencia antes de ofrecer apoyo. El sustento es la tasa ponderada de 7,39 % a los 16 y 17 años frente a 1,29 % a los 12 y 13, los 97 casos muestrales en el tramo mayor y la relevancia predictiva de la edad en Random Forest. La encuesta no identifica qué intervención será efectiva; el piloto debe medir matrícula o continuidad posterior con registros educativos autorizados.')
    sub('2 Diagnóstico de barreras en el contexto rural y del hogar')
    p('Preparar una cartera de verificación local en las 63 jurisdicciones del perfil municipal 4, cuya media de no asistencia censal es 18,71 %, y contrastar barreras de estudio, traslado y apoyo familiar con registros actuales. El perfil 3 aporta una alerta contextual diferente: 48,47 % de carencia media de fuente mejorada de agua. La EH2025 aporta la brecha rural descriptiva y la importancia de área y servicios en XGBoost. El Censo orienta dónde verificar y la encuesta qué factores explorar; ninguno demuestra que un servicio cause inasistencia. Elegir apoyos y presupuesto solo después del diagnóstico local, sin convertir grupos o puntuaciones en asignación automática de beneficios.')
    sub('3 Revisión humana y nueva validación antes de automatizar alertas')
    p('Establecer un protocolo que confirme asistencia y trayectoria mediante registros escolares, con revisión humana, y evaluar prospectivamente una versión del modelo antes de automatizar decisiones. La base empírica es la sensibilidad cero de ambos modelos a 0,5, la baja AP absoluta en prueba y los 11 objetivos positivos que ya completaron secundaria o estudios superiores. Si se estudia otro umbral, debe elegirse con validación y costes de errores, y probarse en datos nuevos. La evaluación debe informar precisión, sensibilidad y carga de revisión por área y sexo, además de posibles daños por clasificaciones erróneas.')
    p('Las tres acciones son propuestas de piloto y validación. No son intervenciones ya aplicadas ni efectos comprobados por este estudio. La priorización individual requiere datos educativos actuales y una decisión profesional contextualizada.')

    page('Aplicación propuesta para la política pública')
    p('Se propone un piloto de 16 semanas dirigido por la autoridad educativa competente, con equipos de orientación y seguimiento como roles funcionales por designar. Territorios, centros participantes, cobertura, recursos y metas se definirán con un diagnóstico local; no se fijan montos ni se atribuye eficacia a una intervención aún no evaluada.')
    table(['Evidencia del estudio','Decisión propuesta','Indicador verificable'],[
        ['16 a 17 años 7,39 % de no asistencia; edad relevante en Random Forest','Pilotar orientación y apoyo después de verificar matrícula y culminación de estudios','Continuidad y revinculación confirmadas a 30 y 60 días, por situación educativa inicial'],
        ['Perfil municipal 4 del Censo 2024: 63 jurisdicciones y 18,71 % de no asistencia media municipal','Confirmar barreras actuales en los territorios antes de elegir apoyos y focalizar recursos','Diagnósticos con barrera confirmada y plan registrado, sobre el total diagnosticado'],
        ['Ambos modelos tienen sensibilidad cero al umbral 0,5 en la reserva','Mantener revisión humana y validar de nuevo antes de automatizar alertas','Precisión, sensibilidad y carga de revisión en datos nuevos, separadas por área y sexo']
    ],[2700,3180,3480])
    table(['Semanas propuestas','Producto y verificación'],[
        ['1 a 4','Marco educativo actual y línea base de matrícula, asistencia y culminación; criterios de elegibilidad registrados'],
        ['5 a 6','Contacto y diagnóstico de barreras; plan de apoyo según necesidad confirmada y recursos disponibles'],
        ['7 a 15','Acompañamiento y comprobaciones de continuidad o revinculación a 30 y 60 días'],
        ['16','Balance de cobertura, resultados y costes observados; decisión documentada de ajustar, ampliar o detener el piloto']
    ],[1800,7560])
    small('El marco operativo debe ser independiente de los microdatos anonimizados. No se intentará identificar ni contactar personas a partir de la EH2025. Las tasas del estudio son referencias de diseño, no la línea base ni la meta de desempeño del piloto.')
    small('Medición: el día 0 es la fecha individual de inclusión y diagnóstico. Continuidad a 60 días = quienes asistían el día 0 y confirman asistencia el día 60 / total que asistía el día 0. Revinculación = quienes no asistían el día 0 y confirman asistencia el día 60 / total con no asistencia el día 0. Mantener los denominadores iniciales y separar estados no confirmados; la falta de seguimiento no prueba inasistencia. Verificar registros de periodo lectivo y documentar vacaciones y fecha efectiva del seguimiento. Cronograma y metas se ajustarán al calendario escolar y la línea base local.')
    small('Una mejora antes y después describe evolución observada. Atribuir impacto al apoyo requerirá un diseño comparativo apropiado. El resultado de esta tarea es el diseño sustentado de una respuesta pública y su evaluación propuesta, no una política ya aplicada ni un problema social ya resuelto.')

    page('Datasets procesados y entrega reproducible')
    p('El repositorio público contiene el dataset municipal procesado que se utiliza realmente para el agrupamiento, en CSV y Parquet. Se entregan las 343 filas con códigos, indicadores, variables transformadas, perfil y proyección; no se trata de una tabla ilustrativa. Los tabulados fuente, el diccionario, el cruce de nombres y códigos y los scripts permiten reconstruirlo.')
    table(['Producto','Unidad y contenido','Destino'],[
      ['dataset_municipal_procesado_2024.csv y .parquet','343 municipios/TIOC; matriz real del clustering municipal, indicadores y perfil','outputs/municipal/ en GitHub'],
      ['dataset_analitico_eh2025_minimizado.csv y .parquet','4.731 adolescentes ; 10 predictores, objetivo y factor; 12 columnas','Complemento académico separado'],
      ['dataset_analitico_eh2025_diseno_restringido.csv y .parquet','Las mismas 4.731 filas; añade estrato y UPM anónimos; 14 columnas','Complemento académico restringido'],
      ['plan_muestral_upm_restringido.csv y .parquet','1.088 parejas estrato-UPM, incluidas 41 sin adolescentes en el dominio','Complemento académico restringido']
    ],[3300,3960,2100])
    p('El dataset individual se entrega antes de la imputación aprendida dentro de cada fold. Se mantienen un ingreso faltante y 1.274 faltantes estructurales de desagüe; no se eliminan filas para producir una tabla aparentemente completa. Las versiones se verificaron mediante lectura de vuelta CSV/Parquet, códigos, pesos, 4.731 filas y 169 objetivos positivos.')
    p('La versión de diseño conserva los grupos necesarios para reproducir las particiones y el plan completo permite incluir UPM con contribución cero fuera del dominio. Se reprodujeron exactamente las particiones y la tasa y su error estándar ajustado. Folio, nro y preguntas que reproducen el objetivo no se distribuyen en estos datasets; no se crean identificadores nuevos.')
    sub('Acceso y separación de paquetes')
    p('El ZIP para GitHub contiene datos municipales agregados, código, resultados e informe. El complemento individual es una copia académica separada para el usuario y su evaluación conforme al protocolo aplicable; no está dentro del ZIP público ni se ha enviado a terceros. ANDA establece mantener condiciones y protocolo de acceso para los datos procesados. La entrega no concede autorización de difusión adicional.')
    small('El cuaderno reconstruye el análisis individual desde las fuentes obtenidas por ANDA y genera el complemento mediante src/delivery_dataset.py en una carpeta excluida. Los hashes y diccionarios documentan integridad y roles. Compartir el complemento únicamente por el canal de evaluación con acceso controlado que corresponda; el dataset municipal público satisface la presencia de un dataset procesado utilizado en el análisis.')

    page('Limitaciones y correspondencia con la tarea')
    p('El diseño transversal describe una condición observada y no permite reconstruir deserción interanual. El rango de edad es una elección analítica. La sensibilidad por estudios completados cambia la estimación y refuerza la necesidad de verificar trayectorias. Los predictores contienen proxies del contexto; no se identificaron efectos causales.')
    p('La precisión se aproxima con estratos y UPM anonimizadas, sin corrección por población finita. Dos estratos solitarios requieren una convención adicional. Los IC ajustados no son estimaciones oficiales; la amplitud regional impide sostener un ranking firme. La muestra de prueba positiva es pequeña y la segmentación tiene separación limitada y no dispone de validación temporal.')
    table(['Requisito','Evidencia en el proyecto'],[['Ingesta y EDA 25 %','Conversión SAV a Parquet, cruce DuckDB auditado y reporte YData-Profiling HTML'],['Exploración 25 %','Mapas departamental EH2025 y municipal Censo 2024, gráficos multivariados y K-Means municipal con perfiles y proyección'],['Modelado y explicación 25 %','Random Forest y XGBoost, CV estratificada y agrupada, reserva, AUC, AP, F1, precisión recall, matrices e importancias'],['Storytelling 25 %','Este informe profesional de hasta 15 páginas y tres recomendaciones de piloto basadas en resultados'],['Especificación municipal','Clustering de 343 municipios/TIOC con fuente oficial complementaria Censo 2024, códigos verificados y mapa municipal'],['Dataset procesado','CSV/Parquet municipal real en outputs; dataset individual real en complemento académico separado'],['GitHub y Moodle','Paquete con estructura requerida preparado. Publicación y envío no realizados']],[2700,6660])
    sub('Privacidad y reproducibilidad')
    p('No se intentó reidentificar personas. Los HTML y tablas públicos contienen agregados y centroides; los identificadores, tablas individuales, scores individuales y entornos están excluidos del paquete para publicar. El dataset municipal de clustering se distribuye en outputs/municipal/; el dataset individual se entrega en un complemento separado y se regenera desde los módulos ANDA.')
    p('Se usó asistencia de IA para preparación y revisión técnica. Los resultados numéricos se obtuvieron mediante ejecución sobre los microdatos recibidos y controles independientes de las fórmulas y del código. No se inventaron resultados ni evidencia de consultas en otras herramientas.')

    page('Fuentes y uso del paquete de entrega')
    refs=[
    'Instituto Nacional de Estadística. (s. f.). Encuesta de Hogares 2025, BOL-INE-EH-2025. Recuperado el 15 de noviembre de 2026 de https://anda.ine.gob.bo/index.php/catalog/256',
    'Instituto Nacional de Estadística. (s. f.). Diseño muestral de la EH2025, secciones 4, 10 y 11, páginas PDF 6 y 12. https://anda.ine.gob.bo/index.php/catalog/256/download/1863',
    'Centers for Disease Control and Prevention. (s. f.). NHANES Tutorials: Variance Estimation. Apoyo metodológico general para dominios; no aporta datos de Bolivia. https://wwwn.cdc.gov/nchs/nhanes/tutorials/varianceestimation.aspx',
    'Lumley, T. (s. f.). Options for the survey package. Convención para estratos con una UPM. https://r-survey.r-forge.r-project.org/survey/html/surveyoptions.html',
    'Instituto Nacional de Estadística. (s. f.). Tabulados municipales de educación y servicios del Censo 2024. https://www.ine.gob.bo/index.php/censos-educacion/ y https://www.ine.gob.bo/index.php/estadisticas-economicas/censos-indicadores/',
    'UDAPE. (s. f.). Atlas 2025 y capa municipal/TIOC pg_v_nbi_2024. https://sigudape.udape.gob.bo/atlas2025/ Acceso y derivación cartográfica documentados en data/municipal/.',
    'geoBoundaries. (s. f.). Bolivia ADM1, límite BOL-ADM1-26024454. Fuente y licencia registradas en data/metadata/cartography_source.json. https://www.geoboundaries.org/api/current/gbOpen/BOL/ADM1/',
    'scikit-learn developers. (s. f.). Average precision score y documentación de modelos. https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html',
    'XGBoost developers. (s. f.). XGBoost Parameters. https://xgboost.readthedocs.io/en/stable/parameter.html',
    ]
    for t in refs:small(t)
    sub('Abrir y comprobar')
    p('Descomprimir el paquete. Abrir docs/Informe_Caso1_EH2025_Final.pdf para lectura y docs/Informe_Caso1_EH2025_Final.docx para edición. Abrir docs/Explorar_resultados.html para elegir los gráficos interactivos. El EDA completo está en outputs/eda_report.html. El cuaderno notebooks/03_Caso1_Completo.ipynb y README.md explican cómo regenerar el análisis con Python 3.12 y las dependencias exactas.')
    sub('Publicar y entregar cuando el trabajo esté revisado')
    small('En GitHub, crear un repositorio público Proyecto_EH2025_ML_Caso1. Con Add file y Upload files, subir el contenido del paquete de publicación conservando data/, notebooks/, src/, outputs/ y docs/ en la raíz, junto a README.md, requirements.txt y .gitignore. Confirmar la carga, comprobar los archivos y copiar la URL del repositorio en Moodle. El ZIP se descomprime antes de subirlo. No subir los microdatos ni la carpeta privada local. Instrucciones ampliadas en docs/Entrega_en_GitHub.md, con enlaces a la documentación oficial de GitHub.')
    small(SOURCE)
    for scope in [doc.styles.element, doc.element]:
        for border in list(scope.iter(qn('w:pBdr'))):
            border.getparent().remove(border)
    target=ROOT/'docs/Informe_Caso1_EH2025_Final.docx';doc.save(target)
    return target

if __name__=='__main__':print(build_report())
