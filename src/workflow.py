"""Etapas separadas para ejecutar el proyecto con microdatos Stata o SPSS."""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path
from .preflight import ROOT, preflight


def prepare(root: Path = ROOT):
    status = preflight(root)
    if status['status'] != 'ready_for_ingestion':
        if not all(x['available'] for x in status['required_microdata'].values()):
            raise FileNotFoundError('Faltan los módulos Persona y Vivienda (.dta o .sav) definidos en data/source_manifest.json.')
    manifest = json.loads((root/'data/source_manifest.json').read_text())
    if not manifest.get('download_source_verified') or manifest.get('microdata_format') not in {'dta', 'sav'}:
        raise ValueError('Registra la procedencia EH2025 y el formato dta o sav en data/source_manifest.json.')
    try:
        date.fromisoformat(manifest['microdata_download_date'])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError('Registra la fecha real de descarga AAAA-MM-DD en data/source_manifest.json.') from exc
    from .ingestion import convert_microdata, create_analysis_table
    from .features import make_features
    import pandas as pd
    private = root/'outputs/private'
    private.mkdir(parents=True, exist_ok=True)
    for name in ['EH2025_Persona', 'EH2025_Vivienda']:
        raw_path = root/status['required_microdata'][name]['relative_path']
        convert_microdata(raw_path, private/f'{name}.parquet',
                      private/f'{name}_source.json')
    create_analysis_table(private/'EH2025_Persona.parquet', private/'EH2025_Vivienda.parquet',
                          private/'joined.parquet', root/'outputs/join_audit.json')
    config = json.loads((root/'config.json').read_text())
    data, audit = make_features(pd.read_parquet(private/'joined.parquet'),
                                config['age_min'], config['age_max'])
    data.to_parquet(private/'analysis.parquet', index=False)
    (root/'outputs/universe_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    status['status'] = 'prepared_with_official_microdata'
    status['real_models_trained'] = False
    (root/'outputs/status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2))
    return audit


def profile(root: Path = ROOT):
    import pandas as pd
    from ydata_profiling import ProfileReport
    from .features import NUMERICAL, CATEGORICAL
    p = root/'outputs/private/analysis.parquet'
    if not p.exists():
        raise FileNotFoundError('Primero ejecuta la etapa prepare con microdatos oficiales.')
    frame = pd.read_parquet(p)[NUMERICAL + CATEGORICAL + ['inasistencia']]
    manifest = json.loads((root/'data/source_manifest.json').read_text())
    citation = ('Fuente: Instituto Nacional de Estadística, Encuesta de Hogares 2025 - '
                'http://anda.ine.gob.bo/index.php/catalog/256. Fecha de acceso: '
                + str(manifest.get('microdata_download_date')) + '.')
    report = ProfileReport(frame, title='EDA EH2025 Caso 1', minimal=True,
                           dataset={'description': citation},
                           samples={'head': 0, 'tail': 0, 'random': 0},
                           duplicates={'head': 0})
    output = root/'outputs/eda_report.html'
    report.to_file(output)
    return {'report': str(output.relative_to(root)),
            'note': 'EDA sin ponderación; no usar como estimaciones poblacionales. Revisar divulgación antes de publicar.'}


def model(root: Path = ROOT):
    import pandas as pd
    from .features import NUMERICAL, CATEGORICAL
    from .modeling import train_models
    p = root/'outputs/private/analysis.parquet'
    if not p.exists():
        raise FileNotFoundError('Primero ejecuta prepare con los datos oficiales.')
    result = train_models(pd.read_parquet(p), NUMERICAL, CATEGORICAL,
                           root/'outputs/model_evaluation', n_splits=5, seed=2026)
    from .model_figures import create_model_figures
    create_model_figures(root/'outputs/model_evaluation')
    state_path = root/'outputs/status.json'
    state = json.loads(state_path.read_text())
    state['real_models_trained'] = True
    state['status'] = 'models_executed_pending_interpretation'
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    return result


def visualize(root: Path = ROOT):
    from .analysis_visuals import create_analysis_visualizations
    p = root/'outputs/private/analysis.parquet'
    if not p.exists():
        raise FileNotFoundError('Primero ejecuta prepare con los datos oficiales.')
    return create_analysis_visualizations(root)


def municipal(root: Path = ROOT):
    from .municipal import create_municipal_analysis
    return create_municipal_analysis(root)


def deliver_dataset(root: Path = ROOT):
    from .delivery_dataset import export_delivery_dataset
    return export_delivery_dataset(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Proyecto EH2025 Caso 1')
    parser.add_argument('stage', choices=['preflight', 'prepare', 'profile', 'model', 'visualize', 'municipal', 'deliver-dataset'])
    args = parser.parse_args()
    actions = {'preflight': preflight, 'prepare': prepare, 'profile': profile,
               'model': model, 'visualize': visualize, 'municipal': municipal,
               'deliver-dataset': deliver_dataset}
    result = actions[args.stage]()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
