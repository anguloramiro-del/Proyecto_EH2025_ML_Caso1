"""Actualiza sensibilidad, portal y estado desde agregados calculados."""
from pathlib import Path
import json
import html
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def finalize(root=ROOT):
    root = Path(root)
    frame = pd.read_parquet(root/'outputs/private/analysis.parquet')
    restricted = frame.loc[~frame['niv_ed'].isin([4, 5])]
    rate = lambda f: float((f.factor*f.inasistencia).sum()/f.factor.sum())
    sensitivity = {
        'full_n': len(frame), 'full_positive': int(frame.inasistencia.sum()),
        'full_rate_weighted': rate(frame),
        'excluded_complete_secondary_n': len(frame)-len(restricted),
        'excluded_positive': int(frame.inasistencia.sum()-restricted.inasistencia.sum()),
        'restricted_n': len(restricted), 'restricted_positive': int(restricted.inasistencia.sum()),
        'restricted_rate_weighted': rate(restricted),
        'scope': 'Sensibilidad descriptiva; sin reentrenamiento ni selección de modelos.',
    }
    (root/'outputs/sensitivity.json').write_text(json.dumps(sensitivity, ensure_ascii=False, indent=2)+'\n')
    universe_path = root/'outputs/universe_audit.json'
    universe = json.loads(universe_path.read_text())
    universe.update(secondary_complete_sensitivity_pending=False,
                    secondary_complete_sensitivity_result='outputs/sensitivity.json')
    universe_path.write_text(json.dumps(universe, ensure_ascii=False, indent=2)+'\n')
    from .model_figures import write_model_summary
    write_model_summary(root/'outputs/model_evaluation')
    figures = [
        ('Mapa departamental y precisión', '../outputs/figures/01_mapa_no_asistencia.html'),
        ('Área y sexo con intervalos', '../outputs/figures/02_area_sexo_ic.html'),
        ('Edad y área con intervalos', '../outputs/figures/03_edad_area_ic.html'),
        ('Edad y no asistencia', '../outputs/figures/04_edad_tasa_ic.html'),
        ('Proyección de centroides', '../outputs/figures/05_clusters_pca_centroides.html'),
        ('Perfiles de los cuatro grupos', '../outputs/figures/06_clusters_perfiles.html'),
        ('No asistencia en los grupos', '../outputs/figures/07_clusters_tasas_ic.html'),
        ('Curvas ROC y precisión recall', '../outputs/model_evaluation/figures/roc_precision_recall.html'),
        ('Matrices de confusión', '../outputs/model_evaluation/figures/confusion_matrices.html'),
        ('Importancia de variables', '../outputs/model_evaluation/figures/feature_importances.html'),
        ('Mapa municipal Censo 2024 y perfiles', '../outputs/municipal/mapa_municipal_2024.html'),
        ('PCA de 343 municipios/TIOC', '../outputs/municipal/pca_municipal_2024.html'),
        ('Indicadores de perfiles municipales', '../outputs/municipal/perfiles_municipales_2024.html'),
    ]
    citation = ('Fuente: Instituto Nacional de Estadística, Encuesta de Hogares 2025 - '
                'http://anda.ine.gob.bo/index.php/catalog/256. Fecha de acceso: 15 de noviembre de 2026.')
    for _, relative in figures:
        file = root/'docs'/relative
        content = file.read_text()
        if '/municipal/' in relative:
            continue
        if 'id="ine-source-note"' not in content:
            footer = (f'<footer id="ine-source-note" style="font:14px Arial;margin:24px"><p>{citation}</p>'
                      '<p>Agregados de la EH2025. No asistencia transversal. '
                      'IC ajustados aproximados, no oficiales.</p></footer></body>')
            file.write_text(content.replace('</body>', footer))
    options = ''.join(f'<option value="{html.escape(url)}">{html.escape(title)}</option>' for title, url in figures)
    links = ''.join(f'<li><a href="{html.escape(url)}" target="_blank">{html.escape(title)}</a></li>' for title, url in figures)
    portal = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resultados del caso 1 EH2025</title>
<style>body{font:17px/1.5 Arial,sans-serif;max-width:1220px;margin:28px auto;padding:0 22px;color:#182d3d}
h1{font-size:29px}select{font:16px Arial;padding:10px;max-width:100%}
iframe{width:100%;height:1050px;border:1px solid #ccd8e0;margin:14px 0}
a{color:#145a86}small{color:#435b69}
.facts{padding:8px 0;border-top:1px solid #d8e2e8;border-bottom:1px solid #d8e2e8}</style>
<h1>No asistencia educativa en Bolivia</h1>
<p>Caso 1 · EH2025 y complemento municipal Censo 2024 · adolescentes de 12 a 17 años · 15 de noviembre de 2026.</p>
<p class="facts"><strong>4.731 adolescentes · tasa ponderada 4,16 % · IC aproximado 2,84 a 5,47 %.</strong><br>
La incertidumbre incluye un ajuste por dos estratos con una sola UPM. Todos los dominios regionales
tienen CV superior a 20 %. Los modelos no detectaron positivos en prueba al umbral de 0,5.</p>
<p><a href="Informe_Caso1_EH2025_Final.pdf">Leer el PDF</a> ·
<a href="Informe_Caso1_EH2025_Final.docx">Abrir el Word editable</a> ·
<a href="../outputs/eda_report.html" target="_blank">Explorar el EDA</a></p>
<p><strong>Componente municipal:</strong> 343 municipios/TIOC del Censo 2024, cartografía UDAPE y cuatro perfiles descriptivos. Las fuentes de 2024 y 2025 se analizan por separado; no forman una serie anual.</p>
<p><a href="../outputs/municipal/dataset_municipal_procesado_2024.csv">Dataset municipal CSV</a> · <a href="../outputs/municipal/dataset_municipal_procesado_2024.parquet">Dataset municipal Parquet</a>. El dataset individual procesado está en un complemento académico separado de acceso controlado.</p>
<p><strong>Uso para política pública:</strong> propuesta de piloto de continuidad y revinculación educativa, con acciones e indicadores a 30 y 60 días. La EH2025 orienta el diseño; la atención individual requiere registros educativos actuales e independientes.</p>
<label for="figure">Elegir visualización</label><br><select id="figure">%%OPTIONS%%</select>
<iframe id="chart" title="Visualización de resultados" src="../outputs/figures/01_mapa_no_asistencia.html"></iframe>
<script>document.getElementById('figure').addEventListener('change',function(){
document.getElementById('chart').src=this.value;});</script>
<details><summary>Abrir gráficos por separado</summary><ul>%%LINKS%%</ul></details>
<p><small>Cartografía referencial geoBoundaries/GeoBolivia de 2015, distribución CC BY 4.0.
Beni y Pando comparten indicador EH2025. La cartografía municipal UDAPE Atlas 2025 se usa como referencia, con fuente y simplificación documentadas. La PCA municipal contiene 343 jurisdicciones agregadas; la PCA individual EH muestra cuatro centroides.</small></p>
<p><small>%%SOURCE%%</small></p></html>"""
    portal = portal.replace('%%OPTIONS%%', options).replace('%%LINKS%%', links).replace('%%SOURCE%%', citation)
    (root/'docs/Explorar_resultados.html').write_text(portal)
    state_path = root/'outputs/status.json'
    state = json.loads(state_path.read_text())
    state.update(status='analysis_completed_publication_pending', real_models_trained=True,
                 eda_completed=True, interactive_visualizations=13, descriptive_visualizations=10,
                 supervised_models=['random_forest', 'xgboost'],
                 municipal_clustering='completed_343_municipalities_TIOC_Censo2024_complement',
                 municipal_source_year=2024, municipality_assignment_to_EH_persons=False,
                 public_processed_dataset='outputs/municipal/dataset_municipal_procesado_2024.parquet',
                 individual_processed_dataset='separate_restricted_academic_complement',
                 github_publication='not_published', report='docs/Informe_Caso1_EH2025_Final.pdf')
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    return {'portal': 'docs/Explorar_resultados.html', 'sensitivity': sensitivity, 'figures': len(figures)}


if __name__ == '__main__':
    print(json.dumps(finalize(), ensure_ascii=False, indent=2))
