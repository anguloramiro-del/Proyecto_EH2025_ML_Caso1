"""Gráficos interactivos y PNG de agregados; ningún punto representa una persona.

Ejecutar: python -m src.analysis_visuals. No modifica el modelado supervisado.
"""
from __future__ import annotations

import json
import os
import textwrap
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from .survey import (DEPARTMENTS, METHOD_NOTE, OFFICIAL_CV_NOTE, SurveyDesign,
                     atomic_csv, atomic_json, atomic_text, code, produce_descriptives)

COLORS = ['#137D88', '#D47732', '#526B97', '#9E5B79', '#70934F']


def source_note(root):
    manifest = json.loads((Path(root) / 'data/source_manifest.json').read_text())
    date = manifest.get('microdata_download_date') or 'fecha pendiente'
    return (f'Fuente: INE, EH2025. Descarga: {date}. Universo propuesto 12–17 años. '
            'No asistencia, no abandono longitudinal.')


def plotting_rates(table):
    """Alias exclusivamente gráficos; CSV mantiene columnas estrictas y adjusted."""
    result = table.copy()
    for alias, original in {
        'se_pp': 'se_adjusted_pp', 'ic95_inf_pct': 'ic95_adjusted_inf_pct',
        'ic95_sup_pct': 'ic95_adjusted_sup_pct', 'cv_pct': 'cv_adjusted_pct',
    }.items():
        result[alias] = pd.to_numeric(result[original], errors='coerce')
    return result


def format_html_figure(fig, source, note=''):
    import plotly.io as pio
    if 'IC95%' in note:
        fig.update_layout(title={'text': fig.layout.title.text + '<br><sup>IC95% aproximado con adjust: 2 estratos solitarios, sin FPC</sup>'})
    fig.update_layout(
        template='plotly_white', font={'family': 'Arial', 'size': 14},
        title={'x': .02, 'font': {'size': 21}},
        margin={'l': 65, 'r': 105, 't': 95, 'b': 175}, height=800,
        paper_bgcolor='white', plot_bgcolor='white',
        annotations=list(fig.layout.annotations or []) + [
            {'text': '<br>'.join(textwrap.wrap(source, 145)) + '<br>' + '<br>'.join(textwrap.wrap(note, 145)),
             'xref': 'paper', 'yref': 'paper', 'x': 0, 'y': -.15,
             'showarrow': False, 'align': 'left', 'xanchor': 'left', 'yanchor': 'top',
             'font': {'size': 11, 'color': '#444444'}},
        ],
    )
    return pio.to_html(fig, full_html=True, include_plotlyjs=True,
                       config={'displaylogo': False, 'responsive': True})


def save_png(fig, path, source, note=''):
    import matplotlib.pyplot as plt
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.text(.04, .035, source, ha='left', va='bottom', fontsize=9, color='#333333')
    if note:
        fig.text(.04, .075, '\n'.join(textwrap.wrap(note, 130)),
                 ha='left', va='bottom', fontsize=9, color='#333333')
    fig.tight_layout(rect=(.02, .17, .99, .96))
    temporary = path.with_name(f'.{path.stem}.{uuid.uuid4().hex}.tmp.png')
    try:
        fig.savefig(temporary, dpi=180, facecolor='white')
        os.replace(temporary, path)
    finally:
        plt.close(fig)
        if temporary.exists():
            temporary.unlink()


def validate_geo(path):
    geo = json.loads(Path(path).read_text())
    ids = set()
    for feature in geo.get('features', []):
        feature['properties']['depto'] = code(feature.get('properties', {}).get('depto'))
        ids.add(feature['properties']['depto'])
        if feature.get('geometry', {}).get('type') not in ['Polygon', 'MultiPolygon']:
            raise ValueError('Se requiere cartografía poligonal departamental.')
    if not set(map(str, range(1, 10))).issubset(ids):
        raise ValueError('La cartografía debe identificar los nueve departamentos con properties.depto.')
    return geo


def polygons(geometry):
    return geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]


def build_clustering(design):
    from sklearn.cluster import KMeans
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
    eligible = design.frame.loc[design.eligible].copy()
    raw = eligible[['s01a_03', 'yhogpc', 'hh_totper']].apply(pd.to_numeric, errors='raise')
    raw = raw.where(np.isfinite(raw) & (raw >= 0))
    if raw.isna().all().any():
        raise ValueError('No se inventan valores para una variable de clustering completamente ausente.')
    X = raw.rename(columns={'s01a_03': 'Edad', 'yhogpc': 'Log ingreso per cápita', 'hh_totper': 'Tamaño del hogar'})
    X['Log ingreso per cápita'] = np.log1p(X['Log ingreso per cápita'])
    imputer = SimpleImputer(strategy='median')
    imputed = imputer.fit_transform(X)
    weights = eligible['factor'].to_numpy(float)
    scaler = StandardScaler().fit(imputed, sample_weight=weights)
    Z = scaler.transform(imputed)
    candidates, admissible = [], []
    for k in range(2, 6):
        model = KMeans(n_clusters=k, random_state=2026, n_init=20)
        lab = model.fit_predict(Z, sample_weight=weights)
        counts = np.bincount(lab, minlength=k)
        score = float(silhouette_score(Z, lab, sample_size=min(2000, len(Z)), random_state=2026))
        accepted = bool((counts >= design.min_n).all())
        candidates.append({'k': k, 'silhouette_unweighted_sample': score,
                           'min_group_sample_n': int(counts.min()), 'accepted': accepted})
        if accepted:
            admissible.append((score, model, lab))
    if not admissible:
        raise ValueError('Ninguna partición KMeans cumple n mínimo; no se publica segmentación inestable por tamaño.')
    score, model, lab = max(admissible, key=lambda item: item[0])
    # Los identificadores de grupo no son una escala de riesgo: se ordenan por ingreso medio.
    weighted_income = {c: float(np.average(raw.loc[lab == c, 'yhogpc'].fillna(raw['yhogpc'].median()),
                                         weights=weights[lab == c])) for c in range(model.n_clusters)}
    order = sorted(weighted_income, key=weighted_income.get)
    remap = {old: new + 1 for new, old in enumerate(order)}
    lab = np.array([remap[v] for v in lab])
    # PCA ponderado para la proyección; se publican únicamente los centroides.
    center = np.average(Z, axis=0, weights=weights)
    covariance = (Z - center).T @ ((Z - center) * weights[:, None]) / weights.sum()
    eigenvalues, vectors = np.linalg.eigh(covariance)
    descending = np.argsort(eigenvalues)[::-1]
    eigenvalues, vectors = eigenvalues[descending], vectors[:, descending]
    proportions = eigenvalues / eigenvalues.sum()
    rows, standardized = [], []
    for c in range(1, model.n_clusters + 1):
        local_mask = lab == c
        full_mask = np.zeros(len(design.frame), dtype=bool)
        full_mask[np.flatnonzero(design.eligible)[local_mask]] = True
        centroid = np.average(Z[local_mask], axis=0, weights=weights[local_mask])
        point = (centroid - center) @ vectors[:, :2]
        row = {'cluster': f'Grupo {c}', 'pca_1': float(point[0]), 'pca_2': float(point[1]),
               **design.estimate(full_mask)}
        for column, name in [('s01a_03', 'edad_media'), ('yhogpc', 'ingreso_per_capita_medio_bs'),
                             ('hh_totper', 'tamano_hogar_medio')]:
            values = raw.loc[local_mask, column]
            valid = values.notna().to_numpy()
            row[name] = float(np.average(values.to_numpy()[valid], weights=weights[local_mask][valid]))
        rows.append(row)
        for name, value in zip(X.columns, centroid):
            standardized.append({'cluster': f'Grupo {c}', 'variable': name, 'centro_estandarizado': float(value)})
    summary = {
        'unit': 'individuos de 12–17 años con etiqueta conocida',
        'selected_k': int(model.n_clusters), 'silhouette_unweighted_sample': float(score),
        'candidate_k': candidates,
        'features': ['edad', 'log1p del ingreso per cápita', 'tamaño del hogar'],
        'target_used_to_fit': False, 'geography_used_to_fit': False,
        'preprocessing': 'Negativos/no finitos a faltante; mediana muestral no ponderada para imputación; log1p ingreso; estandarización ponderada.',
        'weighted_kmeans': True, 'selection': 'Mayor silhouette no ponderada sobre hasta 2000 registros, semilla 2026, entre k=2–5 con cada grupo n>=30.',
        'pca': 'PCA ponderado de las tres variables estandarizadas; solo centroides agregados publicados.',
        'pca_explained_variance': [float(v) for v in proportions],
        'cluster_labels': 'Ordenados por ingreso medio, no por riesgo; números sin significado ordinal de política.',
        'interpretation_limitations': [
            'Segmentación descriptiva dependiente de variables y transformaciones; no diagnóstico ni riesgo causal.',
            'Silhouette mide separación geométrica, no validez causal ni estabilidad temporal.',
            'Las tasas dentro de grupos aprendidos son exploratorias; los IC de razón ajustados por los dos estratos solitarios no incorporan incertidumbre de la selección de k ni del aprendizaje de grupos.',
            'No es clustering municipal; no se identifica municipio de residencia actual.',
            'Las filas de personas y sus coordenadas PCA no se exportan en archivos públicos.',
        ],
    }
    return pd.DataFrame(rows), pd.DataFrame(standardized), summary


def bar_figures(table, x, color, title, source):
    import matplotlib.pyplot as plt
    import plotly.express as px
    tab = table.copy()
    tab['error_sup'] = tab['ic95_sup_pct'] - tab['tasa_pct']
    tab['error_inf'] = tab['tasa_pct'] - tab['ic95_inf_pct']
    hover = ['n_muestra', 'n_no_asistentes', 'poblacion_ponderada', 'ic95_inf_pct', 'ic95_sup_pct', 'cv_pct', 'advertencia']
    interactive = px.bar(tab, x=x, y='tasa_pct', color=color, barmode='group',
                         error_y='error_sup', error_y_minus='error_inf',
                         hover_data=hover, color_discrete_sequence=COLORS, title=title,
                         labels={'tasa_pct': 'No asistencia (%)', x: x.replace('_', ' ').capitalize(), color: color.capitalize(),
                                 'ic95_inf_pct': 'IC95% ajustado inferior', 'ic95_sup_pct': 'IC95% ajustado superior', 'cv_pct': 'CV ajustado (%)'})
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    xvalues = tab[x].drop_duplicates().tolist()
    categories = tab[color].drop_duplicates().tolist()
    width = .75 / len(categories)
    positions = np.arange(len(xvalues))
    for j, category in enumerate(categories):
        sub = tab[tab[color] == category].set_index(x).reindex(xvalues)
        rates = sub['tasa_pct'].to_numpy(float)
        errors = np.vstack([rates - sub['ic95_inf_pct'].to_numpy(float), sub['ic95_sup_pct'].to_numpy(float) - rates])
        xs = positions - .375 + width / 2 + j * width
        ax.bar(xs, rates, width=width, color=COLORS[j], label=category,
               yerr=errors, capsize=4, error_kw={'elinewidth': 1.2})
        for xp, rate, top in zip(xs, rates, sub['ic95_sup_pct'].to_numpy(float)):
            if np.isfinite(rate):
                ax.text(xp, (top if np.isfinite(top) else rate) + .25,
                        f'{rate:.1f}%', ha='center', fontsize=10)
    ax.set_xticks(positions, xvalues)
    ax.set_ylabel('No asistencia (%)', fontsize=12)
    ax.set_title(title + '\nIC95% aproximado con adjust, 2 estratos solitarios', fontsize=16, loc='left', pad=20)
    ax.legend(frameon=False, loc='upper left')
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.18)
    ax.set_axisbelow(True)
    return interactive, fig


def create_analysis_visualizations(project_root):
    os.environ.setdefault('MPLCONFIGDIR', str(Path(project_root) / '.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.patches import Polygon, Patch
    import plotly.express as px
    import plotly.graph_objects as go
    root = Path(project_root)
    design, tables, survey_summary = produce_descriptives(root)
    tables = {name: plotting_rates(table) for name, table in tables.items()}
    geo_path = root / 'data/bolivia_departamentos.geojson'
    if not geo_path.exists():
        raise FileNotFoundError('Descriptivos completos; falta cartografía oficial o autorizada.')
    manifest = json.loads((root / 'data/source_manifest.json').read_text())
    if not manifest.get('cartography_source') or not manifest.get('cartography_license'):
        raise ValueError('Registrar fuente y licencia/condiciones de cartografía antes de producir mapa público.')
    geo = validate_geo(geo_path)
    source = source_note(root)
    output = root / 'outputs/figures'
    output.mkdir(parents=True, exist_ok=True)
    note = 'IC95% Taylor aproximado con convención adjust para 2 estratos solitarios (322 y 821), sin FPC; no es IC oficial. CV ajustado>20% sujeto a evaluación. Supresión n<30: regla del proyecto.'
    completed = []

    def publish(name, interactive, static, extra_note=note):
        atomic_text(output / f'{name}.html', format_html_figure(interactive, source, extra_note))
        save_png(static, output / f'{name}.png', source, extra_note)
        completed.append(name)

    regional = tables['region'].set_index('region')
    mapped = []
    for dept in map(str, range(1, 10)):
        key = '8-9' if dept in ['8', '9'] else dept
        row = regional.loc[DEPARTMENTS[key]].to_dict()
        row.update(depto=dept, dominio=DEPARTMENTS[key])
        mapped.append(row)
    mapped = pd.DataFrame(mapped)
    # Scatter cartesiano de polígonos: no descarga topojson de Plotly ni teselas.
    # La escala en grados es referencial; no se usa para calcular áreas/distancias.
    from plotly.colors import sample_colorscale
    interactive = go.Figure()
    map_max = max(1., float(mapped['tasa_pct'].max()))
    for feature in geo['features']:
        row = mapped[mapped['depto'] == feature['properties']['depto']].iloc[0]
        hover = (f'<b>{row["dominio"]}</b><br>No asistencia: {row["tasa_pct"]:.2f}%'
                 f'<br>IC95% adjusted: {row["ic95_inf_pct"]:.2f}–{row["ic95_sup_pct"]:.2f}%'
                 f'<br>n muestral: {int(row["n_muestra"]):,}'
                 f'<br>Población ponderada: {row["poblacion_ponderada"]:,.0f}'
                 f'<br>CV adjusted: {row["cv_pct"]:.1f}%'
                 f'<br>{"CV>20%: sujeto a evaluación" if row["cv_pct"] > 20 else "IC aproximado con convención adjust"}')
        for polygon in polygons(feature['geometry']):
            ring = np.asarray(polygon[0])
            interactive.add_trace(go.Scatter(x=ring[:, 0], y=ring[:, 1], mode='lines',
                fill='toself', fillcolor=sample_colorscale('YlGnBu', [row['tasa_pct']/map_max])[0],
                line={'color': '#777777', 'width': .8}, hoveron='fills', hovertemplate=hover+'<extra></extra>',
                name=row['dominio'], showlegend=False,
                fillpattern={'shape': '/' if row['cv_pct'] > 20 else '', 'fgopacity': .25}))
    scale_shapes, scale_annotations = [], []
    for step in range(40):
        scale_shapes.append({'type': 'rect', 'xref': 'paper', 'yref': 'paper',
            'x0': 1.02, 'x1': 1.055, 'y0': step/40, 'y1': (step+1)/40,
            'line': {'width': 0}, 'fillcolor': sample_colorscale('YlGnBu', [(step+.5)/40])[0]})
    for step in range(5):
        scale_annotations.append({'xref': 'paper', 'yref': 'paper', 'x': 1.065, 'y': step/4,
            'text': f'{map_max*step/4:.1f}%', 'showarrow': False, 'xanchor': 'left', 'font': {'size': 12}})
    interactive.update_layout(title='No asistencia por dominio geográfico', shapes=scale_shapes,
                              annotations=scale_annotations, dragmode='pan')
    interactive.update_xaxes(visible=False)
    interactive.update_yaxes(visible=False, scaleanchor='x', scaleratio=1)
    fig, ax = plt.subplots(figsize=(9.5, 8))
    normal = Normalize(vmin=0, vmax=max(1., float(mapped['tasa_pct'].max())))
    cmap = plt.get_cmap('YlGnBu')
    for feature in geo['features']:
        dept = feature['properties']['depto']
        row = mapped[mapped['depto'] == dept].iloc[0]
        pts = []
        for polygon in polygons(feature['geometry']):
            ring = np.asarray(polygon[0])[:, :2]
            pts.append(ring)
            ax.add_patch(Polygon(ring, closed=True, facecolor=cmap(normal(row['tasa_pct'])),
                         edgecolor='#777777', linewidth=.7,
                         hatch='///' if pd.notna(row['cv_pct']) and row['cv_pct'] > 20 else None))
        points = np.concatenate(pts)
        cx, cy = (points.min(axis=0) + points.max(axis=0)) / 2
        label = ('Beni' if dept == '8' else 'Pando' if dept == '9' else DEPARTMENTS[dept])
        ax.text(cx, cy, f'{label}\n{row["tasa_pct"]:.1f}%', ha='center', va='center', fontsize=10,
                bbox={'facecolor': 'white', 'alpha': .72, 'edgecolor': 'none', 'pad': 1})
    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.set_axis_off()
    ax.set_title('No asistencia por dominio geográfico', fontsize=18, loc='left', pad=15)
    colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=normal, cmap=cmap), ax=ax, shrink=.65, fraction=.04)
    colorbar.set_label('No asistencia (%)')
    ax.legend(handles=[Patch(facecolor='white', edgecolor='gray', hatch='///', label='CV >20%: sujeto a evaluación')],
              loc='lower left', frameon=False, fontsize=9)
    publish('01_mapa_no_asistencia', interactive, fig,
            note + ' Beni y Pando: una sola estimación conjunta. Cartografía referencial: GeoBolivia 2015, geoBoundaries gbOpen, CC BY 4.0; origen declarado Public Domain. https://www.geoboundaries.org/')

    interactive, static = bar_figures(tables['area_sexo'], 'area', 'sexo', 'No asistencia por área y sexo', source)
    publish('02_area_sexo_ic', interactive, static)
    interactive, static = bar_figures(tables['tramo_area'], 'tramo_edad', 'area', 'No asistencia por tramo de edad y área', source)
    publish('03_edad_area_ic', interactive, static)

    ages = tables['edad'].sort_values('edad').copy()
    ages['error_sup'] = ages['ic95_sup_pct'] - ages['tasa_pct']
    ages['error_inf'] = ages['tasa_pct'] - ages['ic95_inf_pct']
    interactive = px.line(ages, x='edad', y='tasa_pct', markers=True,
                         error_y='error_sup', error_y_minus='error_inf',
                         hover_data=['n_muestra', 'n_no_asistentes', 'poblacion_ponderada', 'cv_pct'],
                         labels={'edad': 'Edad', 'tasa_pct': 'No asistencia (%)'},
                         title='No asistencia según edad cumplida')
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    ax.plot(ages['edad'], ages['tasa_pct'], marker='o', color=COLORS[0], linewidth=2.5)
    ax.fill_between(ages['edad'], ages['ic95_inf_pct'], ages['ic95_sup_pct'], color=COLORS[0], alpha=.15, label='IC95% aproximado')
    for _, row in ages.iterrows():
        ax.annotate(f'{row["tasa_pct"]:.1f}%', (row['edad'], row['tasa_pct']), xytext=(0, 9), textcoords='offset points', ha='center', fontsize=11)
    ax.set_xticks(list(range(12, 18)))
    ax.set_ylabel('No asistencia (%)', fontsize=12)
    ax.set_xlabel('Edad cumplida', fontsize=12)
    ax.set_title('No asistencia según edad cumplida', fontsize=18, loc='left', pad=18)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.18)
    ax.legend(frameon=False)
    publish('04_edad_tasa_ic', interactive, fig, note + ' Comparación transversal de edades; no sigue una cohorte en el tiempo.')

    profiles, standardized, cluster_summary = build_clustering(design)
    atomic_csv(root / 'outputs/descriptive/clustering_perfiles.csv', profiles)
    atomic_csv(root / 'outputs/descriptive/clustering_centroides_estandarizados.csv', standardized)
    atomic_json(root / 'outputs/descriptive/clustering_summary.json', cluster_summary)
    profiles = plotting_rates(profiles)
    variance = cluster_summary['pca_explained_variance']
    pc1, pc2 = f'CP1 ({100*variance[0]:.1f}%)', f'CP2 ({100*variance[1]:.1f}%)'
    interactive = px.scatter(profiles, x='pca_1', y='pca_2', size='poblacion_ponderada', color='cluster',
        text='cluster', size_max=75, hover_data=['n_muestra', 'poblacion_ponderada', 'edad_media', 'ingreso_per_capita_medio_bs', 'tamano_hogar_medio'],
        labels={'pca_1': pc1, 'pca_2': pc2}, color_discrete_sequence=COLORS,
        title='Proyección PCA de centroides de los grupos')
    interactive.update_traces(textposition='top center')
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    sizes = 2800 * profiles['poblacion_ponderada'] / profiles['poblacion_ponderada'].max()
    for i, (_, row) in enumerate(profiles.iterrows()):
        ax.scatter(row['pca_1'], row['pca_2'], s=sizes.iloc[i], color=COLORS[i], alpha=.7, edgecolor='white')
        ax.annotate(f'{row["cluster"]}\nn={int(row["n_muestra"]):,}', (row['pca_1'], row['pca_2']),
                    xytext=(0, 22), textcoords='offset points', ha='center', fontsize=11)
    ax.axhline(0, color='#cccccc', linewidth=.8)
    ax.axvline(0, color='#cccccc', linewidth=.8)
    ax.margins(.25)
    ax.set_xlabel(pc1)
    ax.set_ylabel(pc2)
    ax.set_title('Proyección PCA de centroides de los grupos', fontsize=17, loc='left', pad=18)
    ax.spines[['top', 'right']].set_visible(False)
    cluster_note = 'Solo centroides agregados; tamaño: población ponderada. KMeans descriptivo, no riesgo causal ni agrupamiento municipal.'
    publish('05_clusters_pca_centroides', interactive, fig, cluster_note)

    matrix = standardized.pivot(index='cluster', columns='variable', values='centro_estandarizado')
    interactive = px.imshow(matrix, text_auto='.2f', color_continuous_scale='RdBu_r', color_continuous_midpoint=0,
                            aspect='auto', title='Perfil estandarizado de los grupos', labels={'color': 'Centro z ponderado'})
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    limit = max(abs(matrix.to_numpy()).max(), 1)
    im = ax.imshow(matrix, cmap='RdBu_r', vmin=-limit, vmax=limit, aspect='auto')
    ax.set_xticks(np.arange(len(matrix.columns)), matrix.columns, fontsize=11)
    ax.set_yticks(np.arange(len(matrix.index)), matrix.index, fontsize=12)
    for i in range(len(matrix.index)):
        for j in range(len(matrix.columns)):
            value = matrix.iloc[i, j]
            ax.text(j, i, f'{value:.2f}', ha='center', va='center', fontsize=15,
                    color='white' if abs(value) > .6*limit else 'black')
    fig.colorbar(im, ax=ax, label='Centro estandarizado ponderado', shrink=.8)
    ax.set_title('Perfil estandarizado de los grupos', fontsize=18, loc='left', pad=20)
    publish('06_clusters_perfiles', interactive, fig,
            'Variables: edad, log1p ingreso per cápita y tamaño del hogar. El resultado de asistencia no intervino en la formación de los grupos.')

    interactive = px.bar(profiles, x='cluster', y='tasa_pct', color='cluster',
                         error_y=profiles['ic95_sup_pct']-profiles['tasa_pct'],
                         error_y_minus=profiles['tasa_pct']-profiles['ic95_inf_pct'],
                         hover_data=['n_muestra', 'n_no_asistentes', 'poblacion_ponderada', 'cv_pct', 'advertencia'],
                         title='No asistencia dentro de los grupos descriptivos',
                         labels={'tasa_pct': 'No asistencia (%)'}, color_discrete_sequence=COLORS)
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    rates = profiles['tasa_pct'].to_numpy(float)
    errors = np.vstack([rates-profiles['ic95_inf_pct'], profiles['ic95_sup_pct']-rates])
    ax.bar(profiles['cluster'], rates, yerr=errors, color=COLORS[:len(profiles)], capsize=5)
    for i, row in profiles.iterrows():
        top = row['ic95_sup_pct'] if pd.notna(row['ic95_sup_pct']) else row['tasa_pct']
        ax.text(i, top+.2, f'{row["tasa_pct"]:.1f}%\nn={int(row["n_muestra"]):,}', ha='center', fontsize=11)
    ax.set_ylabel('No asistencia (%)')
    ax.set_title('No asistencia dentro de los grupos descriptivos', fontsize=17, loc='left', pad=20)
    ax.spines[['top', 'right']].set_visible(False)
    publish('07_clusters_tasas_ic', interactive, fig,
            note + ' Exploratorio: estos IC no incorporan la selección de k ni el aprendizaje de los grupos.')

    audit = {
        'interactive_visualizations': [f'{v}.html' for v in completed],
        'static_figures': [f'{v}.png' for v in completed],
        'count': len(completed), 'source': source,
        'privacy': 'Todos los archivos públicos contienen agregados. PCA de centroides; sin registros individuales, IDs o coordenadas individuales.',
        'rates': METHOD_NOTE, 'cv': OFFICIAL_CV_NOTE,
        'geography': 'Beni y Pando: única estimación conjunta replicada visualmente en ambos polígonos; municipio actual no identificado.',
        'map_external_requests': 'Ninguna: polígonos GeoJSON incrustados con trazas cartesianas, sin basemap/topojson/teselas externas.',
        'municipal_clustering_requirement_satisfied': False,
        'clustering': cluster_summary,
        'cartography_source': manifest['cartography_source'],
        'cartography_license': manifest['cartography_license'],
    }
    atomic_json(output / 'visualization_audit.json', audit)
    return audit


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = create_analysis_visualizations(args.project_root)
    print(json.dumps({'count': result['count'], 'figures': result['interactive_visualizations'],
                      'k': result['clustering']['selected_k']}, ensure_ascii=False, indent=2))
