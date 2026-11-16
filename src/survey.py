"""Estimación descriptiva de dominios EH2025 con linealización Taylor.

Se conserva la muestra completa en los cálculos de varianza. Las personas fuera
de cada dominio aportan cero al total linealizado, pero sus UPM permanecen en el
marco observado. Es una aproximación con reemplazo, sin corrección por población
finita; no reproduce ajustes adicionales que pudiera aplicar el INE.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


DEPARTMENTS = {
    '1': 'Chuquisaca', '2': 'La Paz', '3': 'Cochabamba', '4': 'Oruro',
    '5': 'Potosí', '6': 'Tarija', '7': 'Santa Cruz', '8-9': 'Beni y Pando conjunto',
}
METHOD_NOTE = (
    'Tasa ponderada de no asistencia, no abandono longitudinal. IC95% aproximado '
    'por linealización Taylor de una razón, estratos y UPM, sin FPC. En los '
    'estratos solitarios 322 y 821, la varianza estricta no es estimable. Las '
    'columnas adjusted aplican la convención explícita lonely-PSU adjust, '
    'centrando scores UPM en su media global; no son intervalos oficiales. Se conserva '
    'la muestra completa con contribución cero fuera del dominio. Grados de '
    'libertad del IC: UPM menos estratos representados en el dominio. '
    'La garantía de precisión del diseño para pobreza no se traslada al '
    'subgrupo educativo. Supresión de tasas con n<30: regla del proyecto.'
)
OFFICIAL_CV_NOTE = (
    'Diseño INE EH2025, PDF p.12: óptimo CV<10%; bueno 10–15%; regular 16–20%; '
    'CV>20% indicador sujeto a evaluación (rótulo del documento: No significativo). '
    'Ese rótulo no representa una prueba de hipótesis. Se operacionalizan bandas '
    'continuas <10, 10–15, >15–20 y >20 para no dejar sin clasificar el intervalo '
    '15–16. Las dos bandas superiores se identifican como precaución y sujeto a '
    'evaluación, respectivamente.'
)


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_text(text, encoding='utf-8')
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json(path, content):
    atomic_text(path, json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False))


def atomic_csv(path, frame):
    atomic_text(path, frame.to_csv(index=False, na_rep='', float_format='%.8f'))


def code(value):
    if pd.isna(value):
        return 'Sin información'
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
    except (ValueError, TypeError):
        pass
    return str(value)


class SurveyDesign:
    """Diseño observado completo; sin suponer personas independientes."""

    def __init__(self, full: pd.DataFrame, min_n: int = 30):
        needed = {'factor', 'estrato', 'upm', 's01a_03', 'cmasi'}
        if needed - set(full):
            raise ValueError(f'Faltan columnas de diseño: {sorted(needed - set(full))}')
        self.frame = full.reset_index(drop=True).copy()
        if self.frame[['estrato', 'upm']].isna().any().any():
            raise ValueError('No se eliminan silenciosamente registros con diseño faltante.')
        self.weights = pd.to_numeric(self.frame['factor'], errors='raise').to_numpy(float)
        if not np.isfinite(self.weights).all() or (self.weights <= 0).any():
            raise ValueError('Se requieren ponderadores finitos y positivos en toda la muestra.')
        self.strata = self.frame['estrato'].map(code)
        self.psus = self.frame['upm'].map(str)
        if (self.strata.str.strip() == '').any() or (self.psus.str.strip() == '').any():
            raise ValueError('Identificadores de diseño vacíos.')
        self.psu_frame = pd.DataFrame({'estrato': self.strata, 'upm': self.psus}).drop_duplicates()
        counts = self.psu_frame.groupby('estrato', sort=True).size()
        self.stratum_counts = counts
        self.psu_index = pd.MultiIndex.from_frame(self.psu_frame[['estrato', 'upm']])
        self.min_n = int(min_n)
        self.age = pd.to_numeric(self.frame['s01a_03'], errors='raise')
        self.cmasi = pd.to_numeric(self.frame['cmasi'], errors='raise')
        bad = self.age.between(12, 17) & self.cmasi.notna() & ~self.cmasi.isin([1, 2, 3])
        if bad.any():
            raise ValueError('cmasi no documentado dentro del universo propuesto.')
        self.eligible = (self.age.between(12, 17) & self.cmasi.isin([1, 2, 3])).to_numpy()
        self.y = self.cmasi.map({1: 1., 2: 0., 3: 1.}).fillna(0).to_numpy(float)
        cross = self.psu_frame.groupby('upm')['estrato'].nunique()
        self.audit = {
            'source': 'outputs/private/joined.parquet completo',
            'n_full_sample': len(self.frame),
            'n_age_eligible': int(self.age.between(12, 17).sum()),
            'n_labelled_12_17': int(self.eligible.sum()),
            'n_missing_target_in_age_universe': int((self.age.between(12, 17) & self.cmasi.isna()).sum()),
            'strata_count': int(len(counts)),
            'psu_stratum_pairs': int(len(self.psu_frame)),
            'unique_psu_codes': int(self.psus.nunique()),
            'psu_codes_in_multiple_strata': int((cross > 1).sum()),
            'lonely_full_design_strata': [str(v) for v in counts[counts == 1].index],
            'min_psu_per_full_stratum': int(counts.min()),
            'max_psu_per_full_stratum': int(counts.max()),
            'full_design_degrees_freedom': int(len(self.psu_frame) - len(counts)),
            'full_design_stratum_psu_counts': {str(k): int(v) for k, v in counts.items()},
            'variance_estimator': 'Taylor razón; UPM con reemplazo; sin FPC',
            'variance_formula': 'sum_h [m_h/(m_h-1) * sum_j (u_hj - mean_h(u))^2]; u_hj=sum_i w_i*D_i*(y_i-p)/sum_i(w_i*D_i)',
            'full_sample_in_variance': True,
            'outside_domain_contribution': 0,
            'confidence_interval': 't95%, gl=UPM del dominio menos estratos del dominio; límites truncados a [0,100]',
            'min_n_rule': self.min_n,
            'min_n_rule_is_project_choice': True,
            'not_longitudinal_dropout': True,
            'universe_12_17_is_analytical_choice': True,
            'caveats': [METHOD_NOTE, OFFICIAL_CV_NOTE,
                'Sin convención adicional, estratos solitarios impiden estimar la varianza completa. Se preservan columnas estrictas nulas y se añade adjust como sensibilidad explícita.',
                'Si un dominio no tiene eventos, el IC linealizado degenerado no se presenta como certeza; se marca insuficiencia.'],
            'method_support_url': 'https://wwwn.cdc.gov/nchs/nhanes/tutorials/varianceestimation.aspx',
            'method_support_scope': 'Apoyo general para dominios y grados de libertad; se usan variables del diseño EH, no variables NHANES.',
            'official_design_url': 'https://anda.ine.gob.bo/index.php/catalog/256/download/1863',
            'official_design_relevant_pdf_pages': [6, 12],
            'lonely_psu_convention': 'adjust: score UPM solitaria centrado en la media global de scores UPM; contribución cuadrática sin suponer UPM de certeza.',
            'lonely_psu_support_url': 'https://r-survey.r-forge.r-project.org/survey/html/surveyoptions.html',
            'adjusted_intervals_are_official': False,
        }

    def estimate(self, mask=None):
        mask = self.eligible.copy() if mask is None else np.asarray(mask, dtype=bool) & self.eligible
        if len(mask) != len(self.frame):
            raise ValueError('El indicador de dominio debe cubrir toda la muestra.')
        n = int(mask.sum())
        pop = float(self.weights[mask].sum())
        events = int(self.y[mask].sum())
        weighted_events = float((self.weights[mask] * self.y[mask]).sum())
        p = weighted_events / pop if pop > 0 else np.nan
        represented = self.psu_frame.merge(
            pd.DataFrame({'estrato': self.strata[mask], 'upm': self.psus[mask]}).drop_duplicates(),
            on=['estrato', 'upm'], how='inner', validate='one_to_one')
        h_domain = int(represented['estrato'].nunique())
        m_domain = len(represented)
        df_domain = m_domain - h_domain
        variance = np.nan
        variance_adjusted = np.nan
        variance_nonlonely = np.nan
        variance_lonely = np.nan
        if n:
            linear = self.weights * mask * (self.y - p) / pop
            cluster = pd.DataFrame({'estrato': self.strata, 'upm': self.psus, 'linear': linear})
            totals = cluster.groupby(['estrato', 'upm'], sort=False)['linear'].sum().reindex(self.psu_index, fill_value=0)
            variance_nonlonely, variance_lonely = 0., 0.
            grand_mean = float(totals.mean())
            for h, values in totals.groupby(level=0, sort=False):
                m_h = int(self.stratum_counts.loc[h])
                if m_h > 1:
                    variance_nonlonely += float(m_h / (m_h - 1) * ((values - values.mean()) ** 2).sum())
                else:
                    variance_lonely += float(((values - grand_mean) ** 2).sum())
            variance_adjusted = variance_nonlonely + variance_lonely
            if not self.audit['lonely_full_design_strata']:
                variance = variance_nonlonely
        se = np.sqrt(variance) if np.isfinite(variance) else np.nan
        se_adjusted = np.sqrt(variance_adjusted) if np.isfinite(variance_adjusted) else np.nan
        cv = 100 * se / p if np.isfinite(se) and p > 0 else np.nan
        cv_adjusted = 100 * se_adjusted / p if np.isfinite(se_adjusted) and p > 0 else np.nan
        low = high = np.nan
        low_adjusted = high_adjusted = np.nan
        if np.isfinite(se) and df_domain > 0 and 0 < p < 1:
            critical = float(student_t.ppf(.975, df_domain))
            low, high = max(0., p - critical * se), min(1., p + critical * se)
        if np.isfinite(se_adjusted) and df_domain > 0 and 0 < p < 1:
            critical = float(student_t.ppf(.975, df_domain))
            low_adjusted, high_adjusted = max(0., p - critical * se_adjusted), min(1., p + critical * se_adjusted)
        warnings = []
        if n < self.min_n:
            warnings.append('Tasa suprimida: n<30, regla del proyecto')
        if np.isfinite(cv_adjusted) and cv_adjusted > 20:
            warnings.append('CV adjusted>20%: indicador sujeto a evaluación; no implica prueba de hipótesis')
        if events < 5:
            warnings.append('Menos de cinco eventos muestrales; interpretar con cautela')
        if n and (p == 0 or p == 1):
            warnings.append('IC linealizado degenerado no publicado')
        if self.audit['lonely_full_design_strata']:
            warnings.append('IC estricto no estimable; IC adjusted usa convención por estratos solitarios 322 y 821, sin FPC')
        reliability = ('No calculable' if not np.isfinite(cv) else
                       'CV menor de 10%' if cv < 10 else
                       'CV 10 a 15%' if cv <= 15 else
                       'CV mayor de 15 a 20%' if cv <= 20 else
                       'CV mayor de 20% sujeto a evaluación')
        reliability_adjusted = ('No calculable' if not np.isfinite(cv_adjusted) else
                       'CV menor de 10%' if cv_adjusted < 10 else
                       'CV 10 a 15%' if cv_adjusted <= 15 else
                       'CV mayor de 15 a 20%' if cv_adjusted <= 20 else
                       'CV mayor de 20% sujeto a evaluación')
        suppressed = n < self.min_n
        finite = lambda v: float(v) if np.isfinite(v) else None
        return {
            'n_muestra': n, 'n_no_asistentes': events if not suppressed else None,
            'poblacion_ponderada': pop, 'no_asistentes_ponderados': weighted_events if not suppressed else None,
            'tasa_pct': finite(100 * p) if not suppressed else None,
            'se_pp': finite(100 * se) if not suppressed else None,
            'ic95_inf_pct': finite(100 * low) if not suppressed else None,
            'ic95_sup_pct': finite(100 * high) if not suppressed else None,
            'cv_pct': finite(cv) if not suppressed else None,
            'se_adjusted_pp': finite(100 * se_adjusted) if not suppressed else None,
            'ic95_adjusted_inf_pct': finite(100 * low_adjusted) if not suppressed else None,
            'ic95_adjusted_sup_pct': finite(100 * high_adjusted) if not suppressed else None,
            'cv_adjusted_pct': finite(cv_adjusted) if not suppressed else None,
            'calidad_cv_adjusted': reliability_adjusted,
            'variance_nonlonely_component': finite(variance_nonlonely),
            'variance_lonely_adjustment_component': finite(variance_lonely),
            'variance_lonely_adjustment_share_pct': finite(100*variance_lonely/variance_adjusted) if variance_adjusted > 0 else None,
            'calidad_cv': reliability, 'upm_con_dominio': int(m_domain),
            'estratos_con_dominio': h_domain, 'gl_ic': int(df_domain),
            'suprimida': bool(suppressed), 'advertencia': '; '.join(warnings),
        }


def domain_labels(design):
    full = design.frame
    dept = full['depto'].map(code).replace({'8': '8-9', '9': '8-9'})
    bands = pd.cut(design.age, [11, 13, 15, 17], labels=['12–13', '14–15', '16–17'])
    return {
        'region': dept.map(DEPARTMENTS),
        'area': full['area'].map(code).map({'1': 'Urbana', '2': 'Rural'}),
        'sexo': full['s01a_02'].map(code).map({'1': 'Hombre', '2': 'Mujer'}),
        'tramo_edad': bands.astype('object'),
        'edad': design.age,
    }


def estimate_table(design, labels, columns):
    eligible_labels = pd.DataFrame({name: labels[name] for name in columns}).loc[design.eligible]
    unique = eligible_labels.drop_duplicates().sort_values(columns)
    rows = []
    for values in unique.itertuples(index=False, name=None):
        mask = design.eligible.copy()
        record = dict(zip(columns, values))
        for column, value in record.items():
            mask &= np.asarray(labels[column] == value)
        rows.append({**record, **design.estimate(mask)})
    return pd.DataFrame(rows)


def produce_descriptives(project_root):
    root = Path(project_root)
    full = pd.read_parquet(root / 'outputs/private/joined.parquet')
    design = SurveyDesign(full)
    labels = domain_labels(design)
    if any(labels[name].loc[design.eligible].isna().any() for name in ['region', 'area', 'sexo']):
        raise ValueError('Códigos de dominio sin documentar; no se omiten del resumen.')
    tables = {'nacional': pd.DataFrame([{'dominio': 'Bolivia 12–17', **design.estimate()}])}
    groups = {
        'region': ['region'], 'area': ['area'], 'sexo': ['sexo'],
        'tramo_edad': ['tramo_edad'], 'edad': ['edad'],
        'area_sexo': ['area', 'sexo'], 'tramo_area': ['tramo_edad', 'area'],
    }
    for name, columns in groups.items():
        tables[name] = estimate_table(design, labels, columns)
    output = root / 'outputs/descriptive'
    for name, table in tables.items():
        atomic_csv(output / f'tasas_{name}.csv', table)
    atomic_json(output / 'survey_design_audit.json', design.audit)
    all_rates = pd.concat([v.assign(tabla=k) for k, v in tables.items()], ignore_index=True)
    summary = {
        'national': tables['nacional'].iloc[0].to_dict(),
        'full_sample_n': len(full), 'cohort_n': int(design.eligible.sum()),
        'tables': [f'tasas_{n}.csv' for n in tables],
        'rows_with_cv_adjusted_over_20': int((pd.to_numeric(all_rates['cv_adjusted_pct'], errors='coerce') > 20).sum()),
        'rows_suppressed': int(all_rates['suprimida'].sum()),
        'method_note': METHOD_NOTE, 'cv_note': OFFICIAL_CV_NOTE,
        'geography': 'Siete departamentos y dominio conjunto Beni–Pando; municipio actual no identificado.',
        'counts_are_sample_counts': True,
    }
    # pandas/numpy scalar values must be converted to ordinary JSON scalars.
    summary = json.loads(json.dumps(summary, default=lambda v: v.item() if hasattr(v, 'item') else str(v)))
    atomic_json(output / 'survey_summary.json', summary)
    return design, tables, summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    _, _, result = produce_descriptives(args.project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
