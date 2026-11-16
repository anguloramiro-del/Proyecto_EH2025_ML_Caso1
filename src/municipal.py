"""Agrupamiento municipal/TIOC real del Censo 2024 como complemento de EH2025.

Cada jurisdicción recibe el mismo peso. No utiliza personas EH ni asigna
municipios a sus registros. Las tasas observadas son una variable del ajuste:
las diferencias entre perfiles no validan predicción futura ni causalidad.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["no_asistencia_12_17_pct", "ruralidad_12_17_pct",
            "anios_estudio_19_mas", "sin_agua_mejorada_12_17_pct"]
LABELS = ["No asistencia 12–17 (%)", "Ruralidad 12–17 (%)",
          "Años de estudio 19+", "Sin fuente mejorada de agua 12–17 (%)"]
COLORS = ["#167d9a", "#6173a7", "#d8924a", "#9a526f", "#587c44", "#7458a2"]
SOURCE_NOTE = (
    "Fuente: INE, Censo de Población y Vivienda 2024; tabulados de educación "
    "y servicios. Acceso 15/11/2026. Cartografía referencial: UDAPE, Atlas 2025."
)
LIMIT_NOTE = (
    "343 municipios/TIOC; complemento censal 2024 independiente de los modelos EH2025. "
    "Perfiles descriptivos, no predicción de abandono ni selección automática de personas."
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, value) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def _polygons(geometry):
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    if geometry["type"] == "MultiPolygon":
        return [ring for polygon in geometry["coordinates"] for ring in polygon]
    raise ValueError("Se esperaba Polygon o MultiPolygon.")


def _validate_input(data: pd.DataFrame, geo: dict) -> dict:
    from shapely.geometry import shape
    if len(data) != 343 or data["codigo_municipio"].duplicated().any():
        raise ValueError("Se requieren 343 jurisdicciones con código único.")
    if not data["codigo_municipio"].str.fullmatch(r"\d{6}").all():
        raise ValueError("Los códigos deben conservar seis dígitos y sus ceros iniciales.")
    if not data["anio_censo"].eq(2024).all():
        raise ValueError("La fuente municipal debe ser Censo 2024.")
    if data[FEATURES].isna().any().any() or not np.isfinite(data[FEATURES].to_numpy()).all():
        raise ValueError("Las cuatro variables del agrupamiento deben estar completas y finitas.")
    for col in [FEATURES[0], FEATURES[1], FEATURES[3], "agua_mejorada_12_17_pct"]:
        if not data[col].between(0, 100).all():
            raise ValueError(f"Porcentaje fuera de rango: {col}")
    if (data["anios_estudio_19_mas"] < 0).any():
        raise ValueError("Años de estudio negativos.")
    if (data["poblacion_12_17_educacion"] <= 0).any():
        raise ValueError("Denominador educativo vacío o negativo.")
    if not np.allclose(data["asistencia_12_17_pct"] + data["no_asistencia_12_17_pct"],
                       100, rtol=0, atol=1e-10):
        raise ValueError("Asistencia y no asistencia no suman 100.")
    if not data["no_asistencia_12_17_n"].between(0, data["poblacion_12_17_educacion"]).all():
        raise ValueError("Recuentos incompatibles con el denominador educativo.")
    geo_features = geo.get("features", [])
    if len(geo_features) != 343:
        raise ValueError("La geometría no contiene 343 municipios/TIOC.")
    codes = [str(f["properties"]["codigo"]).zfill(6) for f in geo_features]
    if len(set(codes)) != 343 or set(codes) != set(data["codigo_municipio"]):
        raise ValueError("No hay correspondencia 1:1 entre códigos de datos y geometría.")
    invalid = sum(not shape(f["geometry"]).is_valid for f in geo_features)
    if invalid:
        raise ValueError(f"Geometrías inválidas: {invalid}")
    totals = {name: int(data[name].sum()) for name in
              ["poblacion_12_17_educacion", "no_asistencia_12_17_n",
               "poblacion_19_mas_educacion", "poblacion_12_17_escolaridad",
               "poblacion_12_17_viviendas_particulares"]}
    expected = {"poblacion_12_17_educacion": 1265155, "no_asistencia_12_17_n": 84649,
                "poblacion_19_mas_educacion": 7350282, "poblacion_12_17_escolaridad": 1270984,
                "poblacion_12_17_viviendas_particulares": 1272725}
    if totals != expected:
        raise ValueError("Los totales municipales no reproducen los tabulados nacionales verificados.")
    return {"rows": len(data), "unique_codes": 343, "geometry_features": 343,
            "geometry_invalid": invalid, "missing_clustering_features": 0,
            "imputed_values": 0, "national_totals_by_original_universe": totals}


def _write_html(fig, path: Path) -> None:
    fig.update_layout(template="plotly_white", font={"family": "Arial", "size": 12})
    fig.write_html(path, full_html=True, include_plotlyjs=True,
                   config={"responsive": True, "displaylogo": False})
    text = path.read_text()
    footer = (
        '<footer style="font:14px Arial;margin:20px;line-height:1.5">'
        f'<p>{html.escape(SOURCE_NOTE)}</p><p>{html.escape(LIMIT_NOTE)}</p>'
        '<p>Educación: <a href="https://www.ine.gob.bo/index.php/censos-educacion/">INE</a>; '
        'servicios: <a href="https://www.ine.gob.bo/index.php/estadisticas-economicas/censos-indicadores/">INE</a>; '
        'mapa: <a href="https://sigudape.udape.gob.bo/atlas2025/">UDAPE Atlas 2025</a>. '
        'Los denominadores de educación y servicios no son intercambiables. '
        'Una fuente mejorada de agua no equivale a potabilidad certificada.</p>'
        '<p>Cartografía de referencia geoestadística, no deslinde legal. No se afirma '
        'licencia abierta de la capa UDAPE ni autorización irrestricta de redistribución.</p></footer></body>'
    )
    path.write_text(text.replace("</body>", footer))
    if path.stat().st_size >= 25 * 1024 * 1024:
        raise ValueError(f"El HTML excede el límite web de 25 MiB: {path.name}")


def _make_maps(data: pd.DataFrame, geo: dict, output: Path, k: int):
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.patches import Polygon, Patch
    import plotly.graph_objects as go
    from plotly.colors import sample_colorscale
    table = data.set_index("codigo_municipio")
    vmax = float(np.ceil(data["no_asistencia_12_17_pct"].max() / 5) * 5)
    norm = Normalize(0, vmax)
    cmap = plt.get_cmap("YlOrRd")
    features = sorted(geo["features"], key=lambda f: str(f["properties"]["codigo"]).zfill(6))
    fig = go.Figure()
    rate_trace_count = 0
    for feature in features:
        code = str(feature["properties"]["codigo"]).zfill(6)
        row = table.loc[code]
        ratio = float(row["no_asistencia_12_17_pct"]) / vmax
        color = sample_colorscale("YlOrRd", [ratio])[0]
        hover = (f"<b>{html.escape(str(row['municipio_tioc']))}</b> · {html.escape(str(row['departamento']))}"
                 f"<br>Código público: {code}<br>Censo 2024 · municipio/TIOC"
                 f"<br>No asistencia 12–17: {row['no_asistencia_12_17_pct']:.2f}%"
                 f"<br>Población del indicador educativo 12–17: {int(row['poblacion_12_17_educacion']):,}"
                 f"<br>Perfil descriptivo: {row['perfil_municipal']}"
                 f"<br>Ruralidad 12–17: {row['ruralidad_12_17_pct']:.2f}%"
                 f"<br>Años de estudio 19+: {row['anios_estudio_19_mas']:.2f}"
                 f"<br>Sin fuente mejorada de agua 12–17: {row['sin_agua_mejorada_12_17_pct']:.2f}%")
        for ring in _polygons(feature["geometry"]):
            xy = np.asarray(ring)
            fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], mode="lines",
                                    line={"color": "#777777", "width": .25},
                                    fill="toself", fillcolor=color, hoveron="fills",
                                    text=hover, hoverinfo="text", name="", hovertemplate="%{text}<extra></extra>",
                                    showlegend=False, visible=True))
            rate_trace_count += 1
    fig.add_trace(go.Scatter(x=[None, None], y=[None, None], mode="markers",
                            marker={"color": [0, vmax], "colorscale": "YlOrRd",
                                    "cmin": 0, "cmax": vmax, "showscale": True,
                                    "colorbar": {"title": {"text": "No asistencia<br>12–17 (%)"}}},
                            hoverinfo="skip", showlegend=False, visible=True))
    rate_count = rate_trace_count + 1
    for feature in features:
        code = str(feature["properties"]["codigo"]).zfill(6)
        row = table.loc[code]
        profile = int(row["perfil_numero"])
        hover = (f"<b>{html.escape(str(row['municipio_tioc']))}</b> · {html.escape(str(row['departamento']))}"
                 f"<br>Código público: {code}<br>{row['perfil_municipal']} · Censo 2024"
                 f"<br>No asistencia 12–17: {row['no_asistencia_12_17_pct']:.2f}%"
                 f"<br>Ruralidad: {row['ruralidad_12_17_pct']:.2f}%"
                 f"<br>Estudio 19+: {row['anios_estudio_19_mas']:.2f} años"
                 f"<br>Sin fuente mejorada de agua 12–17: {row['sin_agua_mejorada_12_17_pct']:.2f}%")
        for ring in _polygons(feature["geometry"]):
            xy = np.asarray(ring)
            fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], mode="lines",
                                    line={"color": "#777777", "width": .25},
                                    fill="toself", fillcolor=COLORS[profile - 1],
                                    hoveron="fills", text=hover, hoverinfo="text", name="",
                                    hovertemplate="%{text}<extra></extra>", showlegend=False, visible=False))
    for profile in range(1, k+1):
        count = int(data["perfil_numero"].eq(profile).sum())
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                marker={"symbol": "square", "size": 13, "color": COLORS[profile-1]},
                                name=f"Perfil {profile} · {count} jurisdicciones",
                                hoverinfo="skip", showlegend=True, visible=False))
    total = len(fig.data)
    rate_visible = [i < rate_count for i in range(total)]
    profile_visible = [i >= rate_count for i in range(total)]
    fig.update_layout(
        title={"text": "No asistencia educativa municipal/TIOC · Censo 2024", "x": .02, "y": .98, "yanchor": "top"},
        width=1100, height=850, margin={"l": 20, "r": 210, "t": 125, "b": 75},
        updatemenus=[{"type": "dropdown", "direction": "down", "x": 0, "y": 1.10,
                      "buttons": [
                          {"label": "Tasa censal 2024", "method": "update",
                           "args": [{"visible": rate_visible},
                                    {"title.text": "No asistencia educativa municipal/TIOC · Censo 2024"}]},
                          {"label": "Perfil municipal 2024", "method": "update",
                           "args": [{"visible": profile_visible},
                                    {"title.text": "Perfiles municipales/TIOC descriptivos · Censo 2024"}]}]}],
        legend={"x": 1.01, "y": .9},
        annotations=[{"text": "Municipios/TIOC censales. Perfiles contextuales; no riesgo predictivo individual.",
                      "x": .5, "y": -.065, "xref": "paper", "yref": "paper", "showarrow": False,
                      "font": {"size": 11}}],
    )
    fig.update_xaxes(visible=False, range=[-70.1, -57.0], fixedrange=False)
    fig.update_yaxes(visible=False, range=[-23.4, -9.2], scaleanchor="x", scaleratio=1)
    _write_html(fig, output/"mapa_municipal_2024.html")
    for mode, name in [("profile", "mapa_municipal_2024.png"),
                       ("rate", "mapa_municipal_tasa_2024.png")]:
        static, ax = plt.subplots(figsize=(9.5, 8.1))
        for feature in features:
            code = str(feature["properties"]["codigo"]).zfill(6)
            row = table.loc[code]
            color = COLORS[int(row["perfil_numero"])-1] if mode == "profile" else cmap(norm(row["no_asistencia_12_17_pct"]))
            for ring in _polygons(feature["geometry"]):
                ax.add_patch(Polygon(np.asarray(ring), facecolor=color, edgecolor="#666666", linewidth=.15))
        ax.set_xlim(-70.1, -57.0); ax.set_ylim(-23.4, -9.2)
        ax.set_aspect("equal"); ax.axis("off")
        if mode == "profile":
            ax.set_title("Perfiles municipales y TIOC\nCenso 2024 · agrupamiento descriptivo", fontsize=14, pad=12)
            ax.legend(handles=[Patch(facecolor=COLORS[n-1],
                                     label=f"Perfil {n}  n={int(data.perfil_numero.eq(n).sum())}")
                               for n in range(1, k+1)], loc="upper left", bbox_to_anchor=(.97, .97),
                      frameon=False, fontsize=10)
        else:
            ax.set_title("No asistencia educativa de 12 a 17 años\nMunicipios y TIOC · Censo 2024", fontsize=14, pad=12)
            static.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax,
                            fraction=.035, pad=.02, label="No asistencia 12–17 (%)")
        static.text(.06, .065, SOURCE_NOTE, fontsize=8, wrap=True)
        static.text(.06, .035, "Referencia geoestadística; no límites legales. No son tasas municipales EH2025.", fontsize=8)
        static.subplots_adjust(left=.04, right=.82 if mode == "profile" else .91, top=.89, bottom=.12)
        static.savefig(output/name, dpi=180, bbox_inches="tight")
        plt.close(static)
    return {"polygon_traces_per_view": rate_trace_count, "total_traces": total,
            "external_requests_required": False,
            "map_html": "mapa_municipal_2024.html",
            "map_png": ["mapa_municipal_2024.png", "mapa_municipal_tasa_2024.png"]}


def _make_pca_and_heatmap(data, profiles, centers_z, pca, output, k):
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go
    fig = go.Figure()
    static, ax = plt.subplots(figsize=(11.8, 6.7))
    for profile in range(1, k+1):
        part = data.loc[data["perfil_numero"].eq(profile)]
        custom = part[["municipio_tioc", "departamento", "codigo_municipio",
                       "no_asistencia_12_17_pct", "ruralidad_12_17_pct",
                       "anios_estudio_19_mas", "sin_agua_mejorada_12_17_pct"]].to_numpy()
        fig.add_trace(go.Scatter(
            x=part["pca1"], y=part["pca2"], mode="markers", name=f"Perfil {profile} · n={len(part)}",
            marker={"color": COLORS[profile-1], "size": 8, "opacity": .75},
            customdata=custom, hovertemplate=(
                "<b>%{customdata[0]}</b> · %{customdata[1]}<br>Código %{customdata[2]}"
                "<br>No asistencia 12–17: %{customdata[3]:.2f}%"
                "<br>Ruralidad: %{customdata[4]:.2f}%"
                "<br>Años de estudio 19+: %{customdata[5]:.2f}"
                "<br>Sin fuente mejorada de agua: %{customdata[6]:.2f}%<extra>%{fullData.name}</extra>")))
        ax.scatter(part["pca1"], part["pca2"], color=COLORS[profile-1], s=24, alpha=.75,
                   label=f"Perfil {profile} · n={len(part)}")
    centroid_projection = pca.transform(centers_z)
    fig.add_trace(go.Scatter(x=centroid_projection[:, 0], y=centroid_projection[:, 1],
                            mode="markers+text", text=[f"P{i}" for i in range(1, k+1)],
                            textposition="top center", name="Centroides",
                            marker={"symbol": "x", "color": "#111111", "size": 14},
                            hovertemplate="Centroide %{text}<extra></extra>"))
    ax.scatter(centroid_projection[:, 0], centroid_projection[:, 1], c="black", marker="x", s=100, linewidths=2)
    for i, (x, y) in enumerate(centroid_projection, 1):
        ax.annotate(f"P{i}", (x, y), xytext=(5, 6), textcoords="offset points", fontsize=10, weight="bold")
    exp = pca.explained_variance_ratio_
    title = "Proyección de 343 municipios y TIOC · Censo 2024"
    xlabel = f"CP1 ({100*exp[0]:.1f}%)"; ylabel = f"CP2 ({100*exp[1]:.1f}%)"
    fig.update_layout(title=title, width=1100, height=700, xaxis_title=xlabel, yaxis_title=ylabel,
                      legend={"x": 1.01, "y": 1}, margin={"l": 65, "r": 220, "t": 70, "b": 65})
    _write_html(fig, output/"pca_municipal_2024.html")
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel); ax.grid(alpha=.17)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    static.subplots_adjust(left=.08, right=.78, top=.89, bottom=.19)
    static.text(.08, .09, "Cada punto es un municipio/TIOC público; pesos iguales por jurisdicción. No son personas EH2025.", fontsize=9)
    static.text(.08, .045, SOURCE_NOTE, fontsize=8)
    static.savefig(output/"pca_municipal_2024.png", dpi=180, bbox_inches="tight"); plt.close(static)
    heat = go.Figure(go.Heatmap(
        z=centers_z, x=LABELS, y=[f"Perfil {i}" for i in range(1, k+1)],
        colorscale="RdBu_r", zmid=0, text=np.round(centers_z, 2), texttemplate="%{text:.2f}",
        colorbar={"title": "Media<br>estandarizada"},
        hovertemplate="%{y}<br>%{x}<br>Media estandarizada: %{z:.2f}<extra></extra>"))
    heat.update_layout(title="Contexto de los perfiles municipales/TIOC · Censo 2024",
                       height=600, width=1150, margin={"l": 100, "r": 100, "t": 70, "b": 160})
    _write_html(heat, output/"perfiles_municipales_2024.html")
    static, ax = plt.subplots(figsize=(11.5, 5.6))
    vmax = float(np.abs(centers_z).max())
    image = ax.imshow(centers_z, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    labels = ["No asistencia\n12–17 (%)", "Ruralidad\n12–17 (%)",
              "Años de estudio\n19+", "Sin fuente mejorada\nde agua 12–17 (%)"]
    ax.set_xticks(range(4), labels, fontsize=10)
    ax.set_yticks(range(k), [f"Perfil {i}" for i in range(1, k+1)], fontsize=10)
    for i in range(k):
        for j in range(4):
            ax.text(j, i, f"{centers_z[i,j]:.2f}", ha="center", va="center", fontsize=11,
                    color="white" if abs(centers_z[i,j]) > .65*vmax else "black")
    static.colorbar(image, ax=ax, fraction=.035, pad=.03, label="Media estandarizada")
    ax.set_title("Perfiles municipales y TIOC según cuatro variables censales de 2024", fontsize=13, pad=15)
    static.subplots_adjust(left=.10, right=.91, top=.86, bottom=.24)
    static.text(.10, .11, "Cero = media de las 343 jurisdicciones; no son efectos causales ni umbrales de vulnerabilidad.", fontsize=9)
    static.text(.10, .045, SOURCE_NOTE, fontsize=8)
    static.savefig(output/"perfiles_municipales_2024.png", dpi=180, bbox_inches="tight"); plt.close(static)


def create_municipal_analysis(project_root: str | Path = ROOT) -> dict:
    root = Path(project_root).resolve()
    os.environ.setdefault("MPLCONFIGDIR", str(root/".cache/matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    source = root/"data/municipal/municipios_censo2024_indicadores.csv"
    geometry = root/"data/bolivia_municipios_2024.geojson"
    output = root/"outputs/municipal"; output.mkdir(parents=True, exist_ok=True)
    source_hash, geometry_hash = _sha(source), _sha(geometry)
    data = pd.read_csv(source, dtype={"codigo_municipio": "string"})
    data = data.sort_values("codigo_municipio", kind="stable").reset_index(drop=True)
    data["sin_agua_mejorada_12_17_pct"] = 100 - data["agua_mejorada_12_17_pct"]
    geo = json.loads(geometry.read_text())
    validation = _validate_input(data, geo)
    scaler = StandardScaler()
    Z = scaler.fit_transform(data[FEATURES])
    if not np.allclose(Z.mean(axis=0), 0, atol=1e-12):
        raise AssertionError("La estandarización no está centrada.")
    candidates = []
    models = {}
    for k in range(2, 7):
        model = KMeans(n_clusters=k, n_init=20, random_state=2026)
        labels = model.fit_predict(Z)
        counts = np.bincount(labels, minlength=k)
        silhouette = float(silhouette_score(Z, labels))
        candidates.append({"k": k, "silhouette": silhouette,
                           "min_group_n": int(counts.min()), "accepted": bool(counts.min() >= 10)})
        models[k] = model
    accepted = [r for r in candidates if r["accepted"]]
    if not accepted:
        raise ValueError("Ningún k conserva al menos diez jurisdicciones por perfil.")
    choice = max(accepted, key=lambda r: r["silhouette"])
    model = models[choice["k"]]
    old_labels = model.labels_
    ordering = sorted(range(choice["k"]), key=lambda c: float(
        data.loc[old_labels == c, "no_asistencia_12_17_pct"].mean()))
    mapping = {old: new for new, old in enumerate(ordering, start=1)}
    data["perfil_numero"] = pd.Series(old_labels).map(mapping).astype("int64")
    data["perfil_municipal"] = data["perfil_numero"].map(lambda n: f"Perfil {n}")
    for j, name in enumerate(FEATURES):
        data["z_"+name] = Z[:, j]
    pca = PCA(n_components=2, svd_solver="full")
    projection = pca.fit_transform(Z)
    data["pca1"], data["pca2"] = projection[:, 0], projection[:, 1]
    profiles = []
    centers_z = []
    for n, part in data.groupby("perfil_numero", sort=True):
        record = {"perfil_numero": int(n), "perfil_municipal": f"Perfil {n}",
                  "n_municipios_tioc": len(part),
                  "poblacion_12_17_educacion": int(part["poblacion_12_17_educacion"].sum()),
                  "no_asistencia_12_17_n": int(part["no_asistencia_12_17_n"].sum())}
        for name in FEATURES:
            record["media_municipal_"+name] = float(part[name].mean())
        record["tasa_censal_12_17_agrupada_pct"] = (
            100 * record["no_asistencia_12_17_n"] / record["poblacion_12_17_educacion"])
        profiles.append(record)
        centers_z.append(part[["z_"+name for name in FEATURES]].mean().to_numpy())
    profile_frame = pd.DataFrame(profiles).rename(columns={'perfil_municipal': 'perfil', 'n_municipios_tioc': 'n_municipios', 'media_municipal_no_asistencia_12_17_pct': 'no_asistencia_media_municipal_pct', 'media_municipal_ruralidad_12_17_pct': 'ruralidad_media_pct', 'media_municipal_anios_estudio_19_mas': 'anios_estudio_media', 'media_municipal_sin_agua_mejorada_12_17_pct': 'sin_agua_mejorada_media_pct'})
    profiles = profile_frame.to_dict("records")
    centers_z = np.asarray(centers_z)
    stability = []
    for seed in [2027, 2028]:
        other = KMeans(n_clusters=choice["k"], n_init=20, random_state=seed).fit_predict(Z)
        stability.append({"seed": seed, "adjusted_rand_index_vs_2026": float(adjusted_rand_score(old_labels, other))})
    ordered_candidates = sorted(accepted, key=lambda r: r["silhouette"], reverse=True)
    margin = choice["silhouette"] - ordered_candidates[1]["silhouette"]
    data.to_csv(output/"dataset_municipal_procesado_2024.csv", index=False,
                encoding="utf-8-sig", float_format="%.17g", na_rep="")
    data.to_parquet(output/"dataset_municipal_procesado_2024.parquet",
                    index=False, compression="zstd")
    profile_frame.to_csv(output/"perfiles_municipales.csv", index=False,
                         encoding="utf-8-sig", float_format="%.17g")
    centroid_frame = pd.DataFrame(centers_z, columns=["z_"+name for name in FEATURES])
    centroid_frame.insert(0, "perfil_municipal", [f"Perfil {n}" for n in range(1, choice["k"]+1)])
    centroid_frame.to_csv(output/"centroides_municipales_estandarizados.csv", index=False,
                          encoding="utf-8-sig", float_format="%.17g")
    pd.DataFrame(candidates).to_csv(output/"seleccion_k_municipal.csv", index=False, encoding="utf-8-sig")
    pd.testing.assert_frame_equal(data, pd.read_parquet(output/"dataset_municipal_procesado_2024.parquet"),
                                  check_exact=True)
    recovered = pd.read_csv(output/"dataset_municipal_procesado_2024.csv",
                            dtype={"codigo_municipio": "string"}, float_precision="round_trip")
    if not recovered["codigo_municipio"].equals(data["codigo_municipio"]):
        raise AssertionError("El CSV perdió códigos municipales.")
    for name in FEATURES:
        if not np.array_equal(recovered[name].to_numpy(), data[name].to_numpy()):
            raise AssertionError("El CSV alteró una variable del agrupamiento.")
    maps = _make_maps(data, geo, output, choice["k"])
    _make_pca_and_heatmap(data, profile_frame, centers_z, pca, output, choice["k"])
    figures = ["mapa_municipal_2024.html", "pca_municipal_2024.html",
               "perfiles_municipales_2024.html"]
    summary = {
        "unit": "municipio/TIOC", "reference_year": 2024, "rows": 343, "input_validation": validation,
        "source_csv": "data/municipal/municipios_censo2024_indicadores.csv",
        "source_sha256": source_hash, "geometry_sha256": geometry_hash,
        "source_urls": ["https://www.ine.gob.bo/index.php/censos-educacion/",
                        "https://www.ine.gob.bo/index.php/estadisticas-economicas/censos-indicadores/",
                        "https://sigudape.udape.gob.bo/atlas2025/"],
        "features": FEATURES, "feature_labels": LABELS,
        "feature_universes": {
            FEATURES[0]: "Población12–17 de cuadro de asistencia, excluidos exterior/no declaración según notaINE",
            FEATURES[1]: "Población12–17 del mismo cuadro de asistencia",
            FEATURES[2]: "Población19+ de cuadro de promedio de estudio",
            FEATURES[3]: "Población12–17 en viviendas particulares con personas presentes; complemento de fuente mejorada"},
        "standardization": {"method": "StandardScaler media y desviación poblacional por variable, ddof0",
                            "mean": dict(zip(FEATURES, scaler.mean_.tolist())),
                            "scale": dict(zip(FEATURES, scaler.scale_.tolist())), "imputation": "Ninguna"},
        "algorithm": "KMeans", "municipal_weights": "Iguales; una jurisdicción una observación",
        "random_state": 2026, "n_init": 20, "candidate_k": candidates, "selected_k": choice["k"],
        "silhouette": choice["silhouette"], "minimum_profile_n_rule": 10,
        "minimum_profile_n_rule_is_project_choice": True,
        "silhouette_margin_vs_next": float(margin),
        "near_tie": "k4 yk5 casiempatan; el máximo numérico no prueba un número verdadero de perfiles",
        "stability_seeds": stability,
        "stability_scope": "ARI explora sensibilidad de inicialización, no estabilidad temporal ni validez causal",
        "pca_explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "pca_explained_variance": pca.explained_variance_ratio_.tolist(),
        "candidates": candidates,
        "initializer_ari": {str(r["seed"]): r["adjusted_rand_index_vs_2026"] for r in stability},
        "pca_two_components_cumulative": float(pca.explained_variance_ratio_.sum()),
        "centroids_standardized_ordered": centers_z.tolist(), "profiles": profiles,
        "profile_order": "Ascendente por media municipal de no asistencia observada2024; no riesgo futuro",
        "nonattendance_used_to_fit_clusters": True,
        "nonattendance_separation_is_not_independent_validation": True,
        "national_census_nonattendance_pct": float(
            100 * data["no_asistencia_12_17_n"].sum() / data["poblacion_12_17_educacion"].sum()),
        "municipal_rate_mean_unweighted_pct": float(data["no_asistencia_12_17_pct"].mean()),
        "eh2025_people_linked_to_municipalities": False, "individual_records_exported": False,
        "current_municipality_from_EH_inferred": False, "map": maps, "interactive_visualizations": figures,
        "geography_note": "Municipios/TIOC de tabulados Censo2024; capa UDAPE Atlas2025 referencial no legal",
        "geometry_license_note": "Acceso público con atribución; no se asume licencia abierta de redistribución",
        "interpretation_limitations": [
            "Complemento2024 separado de la encuesta EH2025; no son tasas municipales EH2025.",
            "La tasa observada es parte del ajuste y no es predicción de abandono longitudinal.",
            "Los contextos agregados no caracterizan a cada persona ni demuestran causalidad.",
            "Los denominadores de educación y servicios son distintos y no se intercambian.",
            "Fuente de agua mejorada no certifica potabilidad.",
            "El k4 seleccionado casiempata conk5; los perfiles dependen de variables y estandarización.",
            "La geometría no define límites legales; no calcular superficies ni asignar personas con ella."
        ],
        "inputs_unchanged": source_hash == _sha(source) and geometry_hash == _sha(geometry),
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": _sha(p)}
                  for p in output.iterdir() if p.is_file() and p.name != "municipal_summary.json"},
    }
    if not summary["inputs_unchanged"]:
        raise AssertionError("El procesamiento modificó alguna fuente.")
    _json(output/"municipal_summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = create_municipal_analysis(args.project_root)
    print(json.dumps({name: result[name] for name in
                      ["rows", "selected_k", "silhouette", "stability_seeds",
                       "pca_explained_variance_ratio", "profiles"]},
                     ensure_ascii=False, indent=2))
