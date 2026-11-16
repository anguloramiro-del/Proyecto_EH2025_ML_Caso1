"""Clasificación de inasistencia con validación separada por UPM.

Este módulo no descarga datos ni ejecuta entrenamiento al importarlo. Los resultados
son predictivos y no estiman efectos causales de las variables. No se escriben
identificadores, predicciones individuales ni modelos que memoricen registros.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


TARGET = "inasistencia"
GROUP = "upm"
WEIGHT = "factor"
THRESHOLD = 0.5
_FORBIDDEN = {
    TARGET, "cmasi", "folio", "nro", "id_persona", "id_vivienda",
    "id_hogar", "persona_id", "hogar_id", GROUP, "estrato", WEIGHT,
    "asistencia_escolar", "s03a_04", "s03a_05", "s03a_05e",
    "s03a_06a", "s03a_06c",
}


def _validate_data(
    data: pd.DataFrame, numerical: Sequence[str], categorical: Sequence[str],
    n_splits: int,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Se requiere una tabla de análisis no vacía.")
    if not isinstance(n_splits, int) or isinstance(n_splits, bool) or n_splits < 2:
        raise ValueError("n_splits debe ser un entero mayor o igual a dos.")
    numerical, categorical = list(numerical), list(categorical)
    features = numerical + categorical
    if not features or len(features) != len(set(features)):
        raise ValueError("Especifica predictores únicos y listas sin solapamiento.")
    for feature in features:
        base = feature.lower().removeprefix("hh_")
        if base in _FORBIDDEN or base.startswith("s03b_"):
            raise ValueError(f"Predictor excluido por identificación o fuga: {feature}")
    missing = sorted(set(features + [TARGET, GROUP, WEIGHT]) - set(data.columns))
    if missing:
        raise ValueError("Faltan columnas necesarias: " + ", ".join(missing))
    if data[TARGET].isna().any() or not data[TARGET].isin([0, 1]).all():
        raise ValueError("inasistencia debe contener únicamente 0 y 1, sin faltantes.")
    y = data[TARGET].to_numpy(dtype=np.int64)
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("El análisis necesita observaciones de ambas clases.")
    try:
        weights = pd.to_numeric(data[WEIGHT], errors="raise").to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Los factores de expansión deben ser numéricos.") from exc
    if not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError("Los factores de expansión deben ser finitos y positivos.")
    if data[GROUP].isna().any() or data[GROUP].astype(str).str.strip().eq("").any():
        raise ValueError("No se permiten UPM ausentes ni vacías.")
    groups = data[GROUP].astype(str).to_numpy()
    if len(np.unique(groups)) < n_splits:
        raise ValueError("No hay suficientes UPM para la partición solicitada.")
    X = data.loc[:, features].copy()
    for feature in numerical:
        try:
            X[feature] = pd.to_numeric(X[feature], errors="raise").astype(float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"El predictor numérico {feature} contiene texto.") from exc
        if np.isinf(X[feature].to_numpy()).any():
            raise ValueError(f"El predictor {feature} contiene valores infinitos.")
    for feature in categorical:
        # Conserva códigos como categorías y representa los faltantes con np.nan.
        # Esta conversión no aprende estadísticas del conjunto completo.
        X[feature] = X[feature].map(
            lambda value: str(value) if pd.notna(value) else np.nan
        ).astype(object)
    return X, y, groups, weights


def _splits(
    y: np.ndarray, groups: np.ndarray, n_splits: int, seed: int, stage: str,
) -> list[tuple[np.ndarray, np.ndarray]]:
    for value in (0, 1):
        if len(np.unique(groups[y == value])) < n_splits:
            raise ValueError(
                f"{stage}: la clase {value} está presente en menos de {n_splits} UPM. "
                "Revisa la población o reduce n_splits de forma documentada."
            )
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    pairs = list(splitter.split(np.zeros(len(y)), y, groups))
    for number, (fit, validation) in enumerate(pairs, start=1):
        if set(groups[fit]) & set(groups[validation]):
            raise RuntimeError("Se detectó solapamiento de UPM entre particiones.")
        if len(np.unique(y[fit])) != 2 or len(np.unique(y[validation])) != 2:
            raise ValueError(
                f"{stage}, partición {number}: una partición no contiene ambas clases. "
                "No se sustituye por una división que mezcle las UPM."
            )
    return pairs


def _pipeline(model_name: str, numerical: Sequence[str], categorical: Sequence[str], seed: int) -> Pipeline:
    transformers = []
    if numerical:
        transformers.append((
            "num", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            list(numerical),
        ))
    if categorical:
        cat = Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="__FALTANTE__", keep_empty_features=True)),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])
        transformers.append(("cat", cat, list(categorical)))
    if model_name == "random_forest":
        model = RandomForestClassifier(
            n_estimators=200, min_samples_leaf=3, max_features="sqrt",
            n_jobs=1, random_state=seed,
        )
    elif model_name == "xgboost":
        # Importación diferida: permite revisar el módulo sin cargar una biblioteca
        # nativa antes de que el entorno del proyecto esté preparado.
        from xgboost import XGBClassifier
        model = XGBClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, tree_method="hist",
            objective="binary:logistic", eval_metric="logloss",
            n_jobs=1, random_state=seed,
        )
    else:
        raise ValueError("Modelo no reconocido.")
    return Pipeline([
        ("preprocess", ColumnTransformer(transformers, remainder="drop")),
        ("model", model),
    ])


def _probabilities(pipeline: Pipeline, X: pd.DataFrame) -> np.ndarray:
    if not np.array_equal(pipeline.named_steps["model"].classes_, [0, 1]):
        raise RuntimeError("El orden de las clases aprendidas no es el esperado.")
    probabilities = pipeline.predict_proba(X)[:, 1]
    if not np.isfinite(probabilities).all() or np.any((probabilities < 0) | (probabilities > 1)):
        raise RuntimeError("El modelo produjo probabilidades inválidas.")
    return probabilities


def _scores(y: np.ndarray, probability: np.ndarray, weights: np.ndarray | None = None) -> dict:
    predicted = (probability >= THRESHOLD).astype(int)
    return {
        "accuracy": float(accuracy_score(y, predicted, sample_weight=weights)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted, sample_weight=weights)),
        "roc_auc": float(roc_auc_score(y, probability, sample_weight=weights)),
        "average_precision": float(average_precision_score(y, probability, sample_weight=weights)),
        "f1": float(f1_score(y, predicted, sample_weight=weights, zero_division=0)),
        "precision": float(precision_score(y, predicted, sample_weight=weights, zero_division=0)),
        "recall": float(recall_score(y, predicted, sample_weight=weights, zero_division=0)),
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1], sample_weight=weights).tolist(),
    }


def _both_scores(y: np.ndarray, probability: np.ndarray, weights: np.ndarray) -> dict:
    return {"unweighted": _scores(y, probability), "weighted": _scores(y, probability, weights)}


def _aggregate_curves(y: np.ndarray, probability: np.ndarray, weights: np.ndarray | None = None) -> dict:
    """Curvas remuestreadas en una rejilla fija; no exporta scores ni umbrales.

    Las métricas se calculan sobre los scores originales en _scores. Esta rejilla
    es exclusivamente para representar la curva y no debe usarse para recalcular
    AUC o Average Precision. Cada punto expresa una tasa agregada de la reserva.
    """
    fpr, tpr, _ = roc_curve(y, probability, sample_weight=weights)
    precision, recall, _ = precision_recall_curve(y, probability, sample_weight=weights)
    grid = np.linspace(0.0, 1.0, 101)
    return {
        "representation": "Rejilla fija de 101 puntos para visualización; sin umbrales ni scores individuales",
        "fpr": grid.tolist(),
        "tpr": np.interp(grid, fpr, tpr).round(6).tolist(),
        "recall": grid.tolist(),
        "precision": np.interp(grid, recall[::-1], precision[::-1]).round(6).tolist(),
    }


def _fit(pipeline: Pipeline, X: pd.DataFrame, y: np.ndarray, weights: np.ndarray) -> Pipeline:
    return pipeline.fit(X, y, model__sample_weight=weights / weights.mean())


def _importance(pipeline: Pipeline, numerical: Sequence[str], categorical: Sequence[str]) -> pd.DataFrame:
    prep = pipeline.named_steps["preprocess"]
    source_columns = []
    if numerical:
        imputer = prep.named_transformers_["num"]
        source_columns.extend(numerical)
        source_columns.extend(numerical[index] for index in imputer.indicator_.features_)
    if categorical:
        encoder = prep.named_transformers_["cat"].named_steps["onehot"]
        for feature, categories in zip(categorical, encoder.categories_):
            source_columns.extend([feature] * len(categories))
    values = np.asarray(pipeline.named_steps["model"].feature_importances_, dtype=float)
    if len(source_columns) != len(values):
        raise RuntimeError("No se pudo reconstruir el origen de las variables transformadas.")
    if not np.isfinite(values).all():
        raise RuntimeError("La importancia de variables contiene valores no finitos.")
    return (
        pd.DataFrame({"variable": source_columns, "importance": values})
        .groupby("variable", as_index=False)["importance"].sum()
        .sort_values("importance", ascending=False, ignore_index=True)
    )


def train_models(
    data: pd.DataFrame,
    numerical: Sequence[str],
    categorical: Sequence[str],
    output_dir: str | Path,
    n_splits: int = 5,
    seed: int = 2026,
) -> dict:
    """Evalúa Random Forest y XGBoost con preprocesamiento dentro de cada fold.

    El primer fold externo reserva aproximadamente 1/n_splits de las UPM para
    prueba. La selección usa Average Precision ponderada de las predicciones
    fuera de fold sobre el resto; la prueba se consulta después de seleccionar.
    La estratificación agrupada es aproximada y se comprueba en cada partición.
    Las métricas ponderadas no son intervalos de confianza del diseño muestral.
    """
    numerical, categorical = list(numerical), list(categorical)
    X, y, groups, weights = _validate_data(data, numerical, categorical, n_splits)
    train, test = _splits(y, groups, n_splits, seed, "Reserva de prueba")[0]
    X_train = X.iloc[train].reset_index(drop=True)
    y_train, g_train, w_train = y[train], groups[train], weights[train]
    cv = _splits(y_train, g_train, n_splits, seed + 1, "Validación cruzada interna")
    names = ["random_forest", "xgboost"]
    result = {
        "status": "trained",
        "target": TARGET,
        "positive_class": "No matriculado o no asiste según cmasi en la población de análisis",
        "threshold": THRESHOLD,
        "random_state": seed,
        "features": {"numerical": numerical, "categorical": categorical},
        "split": {
            "method": "StratifiedGroupKFold; primer fold para prueba",
            "group_variable": GROUP,
            "n_splits": n_splits,
            "n_train": int(len(train)), "n_test": int(len(test)),
            "n_upm_train": int(len(np.unique(groups[train]))),
            "n_upm_test": int(len(np.unique(groups[test]))),
            "group_overlap": False,
            "train_class_counts": np.bincount(y[train], minlength=2).tolist(),
            "test_class_counts": np.bincount(y[test], minlength=2).tolist(),
            "train_positive_prevalence_unweighted": float(y[train].mean()),
            "train_positive_prevalence_weighted": float(np.average(y[train], weights=weights[train])),
            "test_positive_prevalence_unweighted": float(y[test].mean()),
            "test_positive_prevalence_weighted": float(np.average(y[test], weights=weights[test])),
        },
        "selection_metric": "Average Precision ponderada de predicciones fuera de fold en entrenamiento",
        "models": {},
        "notes": [
            "Imputación y codificación se ajustan solamente con el entrenamiento de cada fold.",
            "Los pesos de ajuste se normalizan por la media del entrenamiento correspondiente.",
            "Umbral 0.5 definido antes de consultar la prueba.",
            "No se publican identificadores ni predicciones individuales.",
            "Las métricas predictivas no son estimaciones de causalidad ni de incertidumbre poblacional.",
            "Las matrices ponderadas suman pesos dentro de su partición; no representan el total nacional.",
            "Las importancias nativas expresan uso predictivo del modelo, no efectos causales.",
            "La referencia de precisión sin información es la prevalencia positiva de la partición evaluada.",
            "Las curvas publicadas son tasas agregadas en rejilla fija; no permiten recuperar umbrales individuales.",
        ],
    }
    for model_name in names:
        oof = np.full(len(train), np.nan)
        fold_results = []
        for fold, (fit, validation) in enumerate(cv, start=1):
            pipeline = _pipeline(model_name, numerical, categorical, seed + fold)
            _fit(pipeline, X_train.iloc[fit], y_train[fit], w_train[fit])
            probability = _probabilities(pipeline, X_train.iloc[validation])
            oof[validation] = probability
            fold_results.append({
                "fold": fold,
                "n_fit": int(len(fit)), "n_validation": int(len(validation)),
                "n_upm_fit": int(len(np.unique(g_train[fit]))),
                "n_upm_validation": int(len(np.unique(g_train[validation]))),
                "group_overlap": False,
                "metrics": _both_scores(y_train[validation], probability, w_train[validation]),
            })
        if np.isnan(oof).any():
            raise RuntimeError("No se obtuvieron predicciones de validación para todas las observaciones.")
        result["models"][model_name] = {
            "cv_folds": fold_results,
            "cv_out_of_fold": _both_scores(y_train, oof, w_train),
        }
    # La elección se fija antes de calcular cualquier métrica en la reserva.
    result["selected_model"] = max(
        names,
        key=lambda name: result["models"][name]["cv_out_of_fold"]["weighted"]["average_precision"],
    )
    # La referencia usa exclusivamente la prevalencia ponderada de entrenamiento.
    # El gráfico PR señala además la prevalencia observada de la reserva como
    # referencia descriptiva; esta no interviene en selección ni ajuste.
    prior = float(np.average(y[train], weights=weights[train]))
    result["baseline"] = {
        "method": "Probabilidad constante igual a la prevalencia ponderada de entrenamiento",
        "positive_probability": prior,
        "predicted_class_at_fixed_threshold": int(prior >= THRESHOLD),
        "holdout": _both_scores(y[test], np.full(len(test), prior), weights[test]),
        "note": "Con prevalencia menor a 0.5 equivale a predecir siempre la clase mayoritaria Asiste.",
    }
    importances = {}
    for model_name in names:
        pipeline = _pipeline(model_name, numerical, categorical, seed)
        _fit(pipeline, X_train, y_train, w_train)
        probability = _probabilities(pipeline, X.iloc[test])
        result["models"][model_name]["holdout"] = _both_scores(y[test], probability, weights[test])
        result["models"][model_name]["holdout_curves"] = {
            "unweighted": _aggregate_curves(y[test], probability),
            "weighted": _aggregate_curves(y[test], probability, weights[test]),
        }
        importances[model_name] = _importance(pipeline, numerical, categorical)
    # Solo se escriben archivos cuando terminaron todos los ajustes y controles.
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for model_name, frame in importances.items():
        frame.to_csv(destination / f"feature_importance_{model_name}.csv", index=False)
    (destination / "model_metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8",
    )
    return result
