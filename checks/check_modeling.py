"""Comprobación aislada con datos de prueba; no produce resultados de EH2025."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.modeling import train_models


def expect_rejection(data, numerical, categorical, folder, expected):
    try:
        train_models(data, numerical, categorical, folder, n_splits=3)
    except ValueError as exc:
        assert expected in str(exc), (expected, str(exc))
    else:
        raise AssertionError("Una entrada inválida fue aceptada.")
    assert not Path(folder, "model_metrics.json").exists()


def main():
    rng = np.random.default_rng(2026)
    size = 480
    signal = rng.normal(size=size)
    label = (signal + rng.normal(scale=0.7, size=size) > 0).astype(int)
    frame = pd.DataFrame({
        "folio": [f"PRUEBA_HOGAR_{i // 2}" for i in range(size)],
        "upm": [f"PRUEBA_UPM_{i // 6}" for i in range(size)],
        "inasistencia": label,
        "factor": rng.uniform(0.3, 5.0, size=size),
        "edad": signal,
        "ingreso": rng.lognormal(size=size),
        "area": rng.choice(["urbana", "rural"], size=size).astype(object),
        "categoria_sin_registro": [None] * size,
    })
    frame.loc[[1, 7, 55], "edad"] = np.nan
    frame.loc[[4, 12], "area"] = np.nan
    with TemporaryDirectory(prefix="eh2025_modeling_check_") as directory:
        base = Path(directory)
        output = base / "valid"
        result = train_models(
            frame, ["edad", "ingreso"], ["area", "categoria_sin_registro"], output, n_splits=3,
        )
        assert result["split"]["group_overlap"] is False
        assert result["split"]["n_train"] + result["split"]["n_test"] == size
        assert result["selected_model"] in {"random_forest", "xgboost"}
        for name, model in result["models"].items():
            assert len(model["cv_folds"]) == 3
            for fold in model["cv_folds"]:
                assert not fold["group_overlap"]
            test = model["holdout"]
            assert 0 <= test["weighted"]["roc_auc"] <= 1
            assert 0 <= test["weighted"]["average_precision"] <= 1
            assert np.asarray(test["unweighted"]["confusion_matrix"]).sum() == result["split"]["n_test"]
            assert test["weighted"]["confusion_matrix"] != test["unweighted"]["confusion_matrix"]
            importance = pd.read_csv(output / f"feature_importance_{name}.csv")
            assert set(importance["variable"]) == {"edad", "ingreso", "area", "categoria_sin_registro"}
            assert (importance["importance"] >= 0).all()
        recorded = json.loads((output / "model_metrics.json").read_text())
        assert recorded["selected_model"] == result["selected_model"]
        assert "PRUEBA_UPM" not in (output / "model_metrics.json").read_text()
        assert "PRUEBA_HOGAR" not in (output / "model_metrics.json").read_text()
        expect_rejection(frame, ["factor"], [], base / "leak", "fuga")
        invalid = frame.copy(); invalid.loc[0, "factor"] = 0
        expect_rejection(invalid, ["edad"], ["area"], base / "weight", "positivos")
        invalid = frame.copy(); invalid.loc[0, "inasistencia"] = np.nan
        expect_rejection(invalid, ["edad"], ["area"], base / "target", "sin faltantes")
        invalid = frame.copy(); invalid.loc[0, "upm"] = np.nan
        expect_rejection(invalid, ["edad"], ["area"], base / "group", "ausentes")
    print("Modelado comprobado con datos de prueba aislados; sin resultados de EH2025.")


if __name__ == "__main__":
    main()
