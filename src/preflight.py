"""Revisión de fuentes y archivos. No genera resultados estadísticos de personas."""
from __future__ import annotations
import json
from pathlib import Path
from hashlib import sha256

ROOT = Path(__file__).resolve().parents[1]


def preflight(root: Path = ROOT) -> dict:
    metadata = json.loads((root/'data/metadata/metadata_EH2025.json').read_text())
    identity = metadata['study_desc']['title_statement']['idno']
    if identity != 'BOL-INE-EH-2025':
        raise ValueError('El catálogo no corresponde a EH2025.')
    dictionary = json.loads((root/'data/metadata/dictionary_verified.json').read_text())
    source_manifest = json.loads((root/'data/source_manifest.json').read_text())
    required = ['EH2025_Persona', 'EH2025_Vivienda']
    state = {}
    for name in required:
        configured = source_manifest.get('raw_module_files', {}).get(name)
        candidates = [root/configured] if configured else [root/'data/raw'/f'{name}{suffix}' for suffix in ['.dta', '.sav']]
        p = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
        present = p.exists() and p.stat().st_size > 0
        state[name] = {'available': present, 'relative_path': str(p.relative_to(root)), 'format': p.suffix.lstrip('.')}
        if present:
            digest = sha256()
            with p.open('rb') as handle:
                for block in iter(lambda: handle.read(1024*1024), b''):
                    digest.update(block)
            state[name]['sha256'] = digest.hexdigest()
    result = {
        'catalog_identity': identity,
        'metadata_access_date': '2026-11-15',
        'microdata_download_date': source_manifest.get('microdata_download_date'),
        'download_source_verified': source_manifest.get('download_source_verified', False),
        'source_verification_method': source_manifest.get('source_verification_method'),
        'case': 1,
        'research_outcome': 'No asistencia educativa, no abandono longitudinal',
        'dictionary_variables': len(dictionary['variables']),
        'catalog_files': [x['name'] for x in dictionary['files']],
        'required_microdata': state,
        'status': 'ready_for_ingestion' if all(x['available'] for x in state.values())
                  else 'awaiting_official_microdata',
        'real_models_trained': False,
        'municipal_clustering': ('completed_343_municipalities_TIOC_Censo2024_complement'
                                 if (root/'outputs/municipal/municipal_summary.json').is_file()
                                 else 'source_included_run_municipal_stage'),
        'github_publication': 'not_published',
    }
    previous_path = root/'outputs/status.json'
    if previous_path.exists():
        previous = json.loads(previous_path.read_text())
        if (previous.get('required_microdata') == state
                and previous.get('real_models_trained') is True
                and result['status'] == 'ready_for_ingestion'):
            result['real_models_trained'] = True
            result['status'] = previous.get('status', 'models_executed_pending_interpretation')
    (root/'outputs').mkdir(exist_ok=True)
    (root/'outputs/status.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    print(json.dumps(preflight(), ensure_ascii=False, indent=2))
