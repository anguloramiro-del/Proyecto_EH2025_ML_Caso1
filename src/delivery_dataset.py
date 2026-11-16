"""Exporta datasets reales de revisión académica con acceso restringido.

No publica datos ni sustituye la descarga autorizada desde ANDA. Conserva los
valores del análisis anterior a la imputación dentro de cada fold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

NUMERICAL = ["s01a_03", "yhogpc", "hh_totper"]
CATEGORICAL = ["s01a_02", "depto", "area", "hh_s06a_07", "hh_s06a_09",
               "hh_s06a_10", "hh_s06a_12"]
FEATURES = NUMERICAL + CATEGORICAL
MINIMAL = FEATURES + ["inasistencia", "factor"]
DESIGN = MINIMAL + ["estrato", "upm"]
EXCLUDED = {"folio", "nro", "cmasi", "s03a_04", "s03b_10", "s03b_11",
            "s03b_12", "niv_ed"}
SOURCE = ("Fuente: Instituto Nacional de Estadística, Encuesta de Hogares 2025 - "
          "http://anda.ine.gob.bo/index.php/catalog/256. Fecha de acceso: "
          "15 de noviembre de 2026.")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                              allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_csv_like(path: Path, expected: pd.DataFrame) -> pd.DataFrame:
    types = {name: "string" for name in expected.columns
             if name in CATEGORICAL or name in {"upm", "estrato"}}
    types.update({name: str(expected[name].dtype) for name in expected.columns
                  if name not in types})
    return pd.read_csv(path, dtype=types, encoding="utf-8-sig",
                       float_precision="round_trip", keep_default_na=True)


def _verify_csv(expected: pd.DataFrame, actual: pd.DataFrame) -> None:
    if list(expected.columns) != list(actual.columns) or len(expected) != len(actual):
        raise AssertionError("CSV no conserva dimensiones o nombres.")
    for name in expected:
        if name in CATEGORICAL or name in {"upm", "estrato"}:
            left = expected[name].astype("string").fillna("__NA__").tolist()
            right = actual[name].astype("string").fillna("__NA__").tolist()
            if left != right:
                raise AssertionError(f"CSV alteró códigos categóricos de {name}.")
        elif not np.array_equal(expected[name].to_numpy(dtype=float),
                                actual[name].to_numpy(dtype=float), equal_nan=True):
            raise AssertionError(f"CSV alteró valores numéricos de {name}.")


def _export_pair(frame: pd.DataFrame, destination: Path, stem: str) -> list[Path]:
    parquet = destination / f"{stem}.parquet"
    csv = destination / f"{stem}.csv"
    tmp = parquet.with_name(parquet.name + ".tmp")
    frame.to_parquet(tmp, index=False, compression="zstd")
    tmp.replace(parquet)
    tmp = csv.with_name(csv.name + ".tmp")
    frame.to_csv(tmp, index=False, encoding="utf-8-sig", float_format="%.17g", na_rep="")
    tmp.replace(csv)
    pd.testing.assert_frame_equal(frame, pd.read_parquet(parquet), check_exact=True)
    _verify_csv(frame, _read_csv_like(csv, frame))
    return [csv, parquet]


def _dictionary(project_root: Path, frame: pd.DataFrame) -> dict:
    dictionary = json.loads((project_root / "data/metadata/dictionary_verified.json").read_text())
    variables = {(v["file"], v["name"]): v for v in dictionary["variables"]}
    records = []
    for name in DESIGN:
        if name == "inasistencia":
            source = {"label": "No asistencia educativa derivada de cmasi",
                      "categories": [{"value": "0", "label": "Asiste (cmasi=2)"},
                                     {"value": "1", "label": "No matriculado o no asiste (cmasi=1/3)"}],
                      "url": next(v["url"] for v in dictionary["variables"]
                                  if v["file"] == "F27" and v["name"] == "cmasi")}
            origin = "Derivada del módulo Persona; no es abandono longitudinal"
        else:
            key = ("F19", name.removeprefix("hh_")) if name.startswith("hh_") else ("F27", name)
            source = variables[key]
            origin = "Vivienda" if key[0] == "F19" else "Persona"
        role = ("predictor" if name in FEATURES else "objetivo" if name == "inasistencia"
                else "ponderador" if name == "factor" else "diseño y validación; no predictor")
        unit = ("años cumplidos" if name == "s01a_03" else "Bs por persona por mes"
                if name == "yhogpc" else "personas del hogar" if name == "hh_totper"
                else "factor de expansión" if name == "factor" else "código")
        missing = ("No imputados; un faltante en ingreso. La mediana se aprende dentro de cada fold."
                   if name == "yhogpc" else
                   "1.274 nulos en la cohorte: patrón compatible con salto del formulario; no convertir a cero."
                   if name == "hh_s06a_10" else "Nulos conservados como nulos; no se inventan respuestas.")
        records.append({"name": name, "label": source["label"], "role": role,
                        "dtype_parquet": str(frame[name].dtype), "unit": unit,
                        "origin": origin, "source_url": source.get("url"),
                        "categories": source.get("categories", []),
                        "missing_note": missing,
                        "included_in_minimal": name in MINIMAL,
                        "distribution": "académica restringida; no publicar en GitHub"})
    return {"source": SOURCE, "universe": "Adolescentes de 12 a 17 años inclusive con cmasi conocido",
            "target_derivation": "cmasi1/3→1; cmasi2→0; etiquetas faltantes no imputadas",
            "imputation": "No se exportan predictores imputados globalmente",
            "variables": records}


def _reproduction_checks(root: Path, original: pd.DataFrame,
                         exported: pd.DataFrame, plan: pd.DataFrame) -> dict:
    """Contraste independiente del diseño suficiente y de las particiones."""
    from sklearn.model_selection import StratifiedGroupKFold
    y = original["inasistencia"].to_numpy()
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=2026)
    left = list(splitter.split(np.zeros(len(y)), y, original["upm"].astype(str)))
    right = list(splitter.split(np.zeros(len(y)), exported["inasistencia"].to_numpy(),
                                exported["upm"].astype(str)))
    same = all(np.array_equal(a, c) and np.array_equal(b, d)
               for (a, b), (c, d) in zip(left, right))
    if not same:
        raise AssertionError("La entrega cambia las particiones agrupadas.")
    weight = exported["factor"]
    proportion = float((weight * exported["inasistencia"]).sum() / weight.sum())
    scores = exported[["estrato", "upm"]].copy()
    scores["score"] = weight * (exported["inasistencia"] - proportion) / weight.sum()
    sums = scores.groupby(["estrato", "upm"], as_index=False)["score"].sum()
    all_psus = plan.merge(sums, on=["estrato", "upm"], how="left").fillna({"score": 0.})
    global_mean = float(all_psus["score"].mean())
    nonlonely = lonely_adjust = 0.
    lonely_strata = []
    for stratum, units in all_psus.groupby("estrato"):
        m = len(units)
        if m == 1:
            lonely_strata.append(str(stratum))
            lonely_adjust += float(((units["score"] - global_mean)**2).sum())
        else:
            nonlonely += float(m / (m-1) * ((units["score"] - units["score"].mean())**2).sum())
    se_pp = float(np.sqrt(nonlonely + lonely_adjust) * 100)
    expected_file = root / "outputs/descriptive/survey_summary.json"
    reference_match = None
    if expected_file.exists():
        expected = json.loads(expected_file.read_text())["national"]
        reference_match = bool(np.isclose(proportion * 100, expected["tasa_pct"], atol=1e-12, rtol=0)
                               and np.isclose(se_pp, expected["se_adjusted_pp"], atol=1e-12, rtol=0))
        if not reference_match:
            raise AssertionError("Cohorte y plan exportados no reproducen el estimador de referencia.")
    cohort_pairs = set(map(tuple, exported[["estrato", "upm"]].drop_duplicates().to_numpy()))
    full_pairs = set(map(tuple, plan.to_numpy()))
    return {
        "model_grouped_folds_identical": same,
        "taylor_rate_pct": proportion * 100, "taylor_se_adjusted_pp": se_pp,
        "taylor_strict_variance_estimable": not bool(lonely_strata),
        "lonely_strata": lonely_strata,
        "taylor_convention": "adjust global explícito para UPM solitarias, sin FPC; no intervalo oficial",
        "taylor_reference_match": reference_match,
        "full_plan_psus_outside_cohort": len(full_pairs - cohort_pairs),
    }


def export_delivery_dataset(project_root: str | Path, destination: str | Path | None = None) -> dict:
    root = Path(project_root).resolve()
    destination = (Path(destination).resolve() if destination else
                   root / "outputs/entrega_restringida")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / "data/source_manifest.json").read_text())
    if manifest.get("catalog_identity") != "BOL-INE-EH-2025":
        raise ValueError("El manifiesto de origen no identifica BOL-INE-EH-2025.")
    source_analysis = root / "outputs/private/analysis.parquet"
    source_joined = root / "outputs/private/joined.parquet"
    original_hashes = {source_analysis.name: sha256(source_analysis),
                       source_joined.name: sha256(source_joined)}
    frame = pd.read_parquet(source_analysis)
    missing = set(DESIGN) - set(frame.columns)
    if missing:
        raise ValueError(f"Faltan variables del análisis: {sorted(missing)}")
    if len(frame) != 4731 or int(frame["inasistencia"].sum()) != 169:
        raise ValueError("La fuente no coincide con el universo verificado de EH2025 Caso1.")
    if (not frame["inasistencia"].isin([0, 1]).all()
            or not frame["s01a_03"].between(12, 17, inclusive="both").all()):
        raise ValueError("Objetivo o edades no corresponden al universo documentado.")
    if (not np.isfinite(frame["factor"]).all() or (frame["factor"] <= 0).any()
            or frame[["upm", "estrato"]].isna().any().any()):
        raise ValueError("Ponderador o campos de diseño inválidos.")
    definition = _dictionary(root, frame)
    for record in definition["variables"]:
        if record["name"] in CATEGORICAL:
            codes = {c["value"] for c in record["categories"] if c["value"] != "Sysmiss"}
            actual = set(frame[record["name"]].dropna().astype(str))
            if actual - codes:
                raise ValueError(f"Códigos no documentados en {record['name']}: {actual - codes}")
    minimal = frame.loc[:, MINIMAL].copy()
    design = frame.loc[:, DESIGN].copy()
    if set(minimal.columns) & EXCLUDED or set(design.columns) & EXCLUDED:
        raise AssertionError("Se intentó exportar un identificador personal o variable excluida.")
    files = _export_pair(minimal, destination, "dataset_analitico_eh2025_minimizado")
    files += _export_pair(design, destination, "dataset_analitico_eh2025_diseno_restringido")
    full_design = pd.read_parquet(source_joined, columns=["estrato", "upm"])
    if full_design.isna().any().any():
        raise ValueError("El plan muestral contiene valores nulos.")
    full_design = (full_design.drop_duplicates()
                   .sort_values(["estrato", "upm"], kind="stable").reset_index(drop=True))
    if full_design.groupby("upm")["estrato"].nunique().max() != 1:
        raise ValueError("Una UPM aparece en varios estratos.")
    if len(full_design) != 1088 or full_design["estrato"].nunique() != 70:
        raise ValueError("El plan completo no coincide con 1.088 UPM y 70 estratos.")
    if not set(map(tuple, design[["estrato", "upm"]].drop_duplicates().to_numpy())).issubset(
            set(map(tuple, full_design.to_numpy()))):
        raise AssertionError("Una UPM de la cohorte falta en el plan completo.")
    files += _export_pair(full_design, destination, "plan_muestral_upm_restringido")
    reproduction = _reproduction_checks(
        root, frame, pd.read_parquet(destination / "dataset_analitico_eh2025_diseno_restringido.parquet"),
        pd.read_parquet(destination / "plan_muestral_upm_restringido.parquet"))
    atomic_json(destination / "diccionario_dataset_analitico.json", definition)
    dictionary_csv = pd.DataFrame([{**v, "categories": json.dumps(v["categories"], ensure_ascii=False)}
                                    for v in definition["variables"]])
    dictionary_csv.to_csv(destination / "diccionario_dataset_analitico.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "review_date": "2026-11-15", "dataset_is_real_eh2025": True,
        "unit": "persona", "rows": len(frame), "positive_count": int(frame["inasistencia"].sum()),
        "target_missing": int(frame["inasistencia"].isna().sum()),
        "age_min": float(frame["s01a_03"].min()), "age_max": float(frame["s01a_03"].max()),
        "minimal_columns": MINIMAL, "restricted_design_columns": DESIGN,
        "personal_keys_excluded": ["folio", "nro"], "new_identifiers_created": False,
        "sampling_codes_retained_only_in_restricted_design_version": ["estrato", "upm"],
        "cohort_psu_count": int(frame["upm"].nunique()),
        "full_design_psu_count": len(full_design), "full_design_strata": int(full_design["estrato"].nunique()),
        "weighted_population_sum": float(frame["factor"].sum()),
        "weighted_positive_sum": float((frame["factor"] * frame["inasistencia"]).sum()),
        "missing_counts": frame[MINIMAL].isna().sum().astype(int).to_dict(),
        "duplicate_feature_rows_not_dropped": True, "imputed_globally": False,
        "csv_roundtrip": "exact numerical values and categorical codes verified",
        "parquet_roundtrip": "exact DataFrame verified",
        "input_hashes": original_hashes,
        "input_files_unchanged": original_hashes == {
            source_analysis.name: sha256(source_analysis), source_joined.name: sha256(source_joined)},
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in files},
        "public_distribution": False,
        "access_protocol": "Conservar condiciones y protocolo de acceso de ANDA; no subir filas individuales a GitHub.",
        "current_municipality": "No identificado; las personas no se asignan a municipios.",
        "reproduction_checks": reproduction,
    }
    if not metadata["input_files_unchanged"]:
        raise AssertionError("La exportación alteró una fuente.")
    atomic_json(destination / "auditoria_entrega_dataset.json", metadata)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    result = export_delivery_dataset(args.project_root, args.output_dir)
    print(json.dumps({"rows": result["rows"], "positive_count": result["positive_count"],
                      "files": list(result["files"]), "roundtrip": "passed",
                      "public_distribution": False}, ensure_ascii=False, indent=2))
