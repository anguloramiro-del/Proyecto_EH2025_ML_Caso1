"""Definición explícita del universo y del resultado, sin imputar la etiqueta."""
from __future__ import annotations

import numpy as np
import pandas as pd

NUMERICAL = ['s01a_03', 'yhogpc', 'hh_totper']
CATEGORICAL = ['s01a_02', 'depto', 'area', 'hh_s06a_07', 'hh_s06a_09',
               'hh_s06a_10', 'hh_s06a_12']
FORBIDDEN = {'folio', 'nro', 'upm', 'estrato', 'factor', 'cmasi', 'inasistencia',
             's03a_04', 's03a_05', 's03b_10', 's03b_11', 's03b_12', 'niv_ed'}


def make_features(frame: pd.DataFrame, age_min: int = 12, age_max: int = 17):
    required = set(NUMERICAL + CATEGORICAL + ['cmasi', 'factor', 'upm', 'folio', 'nro'])
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f'Faltan columnas verificadas: {sorted(missing)}')
    if not 4 <= age_min <= age_max <= 98:
        raise ValueError('El recorte de edad debe estar dentro del universo educativo.')
    age = pd.to_numeric(frame['s01a_03'], errors='raise')
    eligible = frame.loc[age.between(age_min, age_max, inclusive='both')].copy()
    codes = pd.to_numeric(eligible['cmasi'], errors='raise')
    invalid = codes.notna() & ~codes.isin([1, 2, 3])
    if invalid.any():
        raise ValueError('cmasi contiene códigos no documentados; revisar antes de continuar.')
    eligible['inasistencia'] = codes.map({1: 1, 2: 0, 3: 1})
    report = {
        'age_min': age_min, 'age_max': age_max,
        'universe_is_analytical_choice': True,
        'n_joined': len(frame), 'n_age_eligible': len(eligible),
        'n_target_missing': int(eligible['inasistencia'].isna().sum()),
        'n_not_enrolled': int((codes == 1).sum()),
        'n_attending': int((codes == 2).sum()),
        'n_enrolled_not_attending': int((codes == 3).sum()),
        'not_longitudinal_dropout': True,
    }
    labelled = eligible.loc[eligible['inasistencia'].notna()].copy()
    labelled['inasistencia'] = labelled['inasistencia'].astype('int64')
    weights = pd.to_numeric(labelled['factor'], errors='raise')
    if weights.isna().any() or (~np.isfinite(weights)).any() or (weights <= 0).any():
        raise ValueError('Los factores deben ser finitos y positivos en el universo analítico.')
    if labelled[['upm', 'folio', 'nro']].isna().any().any():
        raise ValueError('Faltan identificadores necesarios para controlar unidades relacionadas.')
    for name in NUMERICAL:
        labelled[name] = pd.to_numeric(labelled[name], errors='raise')
        labelled.loc[~np.isfinite(labelled[name]) | (labelled[name] < 0), name] = np.nan
    for name in CATEGORICAL:
        values = labelled[name]
        labelled[name] = values.map(lambda v: np.nan if pd.isna(v) else str(int(v))
                                   if isinstance(v, (int, float, np.integer, np.floating))
                                   and float(v).is_integer() else str(v)).astype(object)
    if set(NUMERICAL + CATEGORICAL) & FORBIDDEN:
        raise AssertionError('Fuga de información en el listado de predictores.')
    report['n_labelled'] = len(labelled)
    report['secondary_complete_sensitivity_pending'] = 'niv_ed' in labelled.columns
    return labelled, report
