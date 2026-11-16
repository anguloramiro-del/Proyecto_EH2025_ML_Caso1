"""Figuras de evaluación a partir de métricas y tasas agregadas.

No necesita cargar microdatos ni predicciones individuales. Produce PNG e HTML
para ROC, precisión-recall, matrices de confusión e importancia de variables.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

NAMES = {"random_forest": "Random Forest", "xgboost": "XGBoost"}
COLORS = {"random_forest": "#245FA6", "xgboost": "#C05621"}
LABELS = {
    "s01a_03": "Edad",
    "yhogpc": "Ingreso del hogar por persona",
    "hh_totper": "Número de miembros del hogar",
    "s01a_02": "Sexo registrado",
    "depto": "Departamento",
    "area": "Área urbana o rural",
    "hh_s06a_07": "Fuente de agua",
    "hh_s06a_09": "Tipo de servicio sanitario",
    "hh_s06a_10": "Desagüe del servicio sanitario",
    "hh_s06a_12": "Acceso a electricidad",
}


def write_model_summary(evaluation_dir: str | Path) -> dict:
    """Resumen reproducible de resultados y límites, siempre desde agregados."""
    source = Path(evaluation_dir)
    result = json.loads((source / "model_metrics.json").read_text())
    rows = []
    for name, model in result["models"].items():
        weighted = model["holdout"]["weighted"]
        matrix = model["holdout"]["unweighted"]["confusion_matrix"]
        rows.append({
            "modelo": NAMES[name],
            "ap_cv_ponderada": model["cv_out_of_fold"]["weighted"]["average_precision"],
            **{f"prueba_{metric}_ponderada": weighted[metric] for metric in [
                "roc_auc", "average_precision", "accuracy", "balanced_accuracy", "precision", "recall", "f1"]},
            "tn": matrix[0][0], "fp": matrix[0][1], "fn": matrix[1][0], "tp": matrix[1][1],
        })
    baseline = result["baseline"]["holdout"]["weighted"]
    matrix = result["baseline"]["holdout"]["unweighted"]["confusion_matrix"]
    rows.append({
        "modelo": "Referencia de prevalencia de entrenamiento",
        "ap_cv_ponderada": None,
        **{f"prueba_{metric}_ponderada": baseline[metric] for metric in [
            "roc_auc", "average_precision", "accuracy", "balanced_accuracy", "precision", "recall", "f1"]},
        "tn": matrix[0][0], "fp": matrix[0][1], "fn": matrix[1][0], "tp": matrix[1][1],
    })
    pd.DataFrame(rows).to_csv(source / "model_comparison.csv", index=False)
    selected = result["selected_model"]
    chosen = result["models"][selected]["holdout"]["weighted"]
    reference = result["split"]["test_positive_prevalence_weighted"]
    zero_detected = all(m["holdout"]["unweighted"]["confusion_matrix"][1][1] == 0
                        for m in result["models"].values())
    detection_note = (
        f"Al umbral fijo {result['threshold']}, la reserva no contiene verdaderos positivos detectados por ninguno de los modelos."
        if zero_detected else
        f"La detección al umbral fijo {result['threshold']} se documenta en las matrices de confusión; no se ajustó el umbral con la reserva."
    )
    ranking_note = (
        "El ordenamiento de scores mejora la referencia de prevalencia, pero por sí solo no valida una herramienta operativa al umbral fijado."
        if chosen["average_precision"] > reference else
        "La Average Precision del modelo seleccionado no mejora la referencia de prevalencia en la reserva."
    )
    summary = {
        "selected_model": selected,
        "selection_was_prior_to_holdout_metrics": True,
        "threshold": result["threshold"],
        "holdout_n": result["split"]["n_test"],
        "holdout_positive_n": result["split"]["test_class_counts"][1],
        "holdout_positive_prevalence_weighted": reference,
        "selected_ap_lift_over_prevalence": chosen["average_precision"] / reference,
        "observations": [
            "La elección se basó en Average Precision ponderada de validación cruzada, no en la reserva.",
            detection_note,
            "La exactitud debe leerse junto a la prevalencia, recall, F1 y exactitud balanceada; una clase dominante puede producir exactitud alta sin detección positiva.",
            ranking_note,
            f"La reserva contiene {result['split']['test_class_counts'][1]} casos positivos; no se estimaron intervalos de confianza ni significación de diferencias entre modelos.",
            "La partición por UPM evalúa rendimiento en UPM reservadas de la misma encuesta, no validación temporal ni predicción de abandono futuro.",
            "Cualquier estudio de umbrales debe realizarse dentro de entrenamiento/validación y confirmarse con una nueva reserva independiente.",
            "La importancia de una variable no informa la dirección del vínculo ni identifica un efecto causal.",
        ],
        "importance_definitions": {
            "random_forest": "Reducción normalizada de impureza acumulada en los árboles; puede favorecer variables continuas o de alta cardinalidad.",
            "xgboost": "Gain normalizado por variable transformada, valor predeterminado comprobado en XGBoost 3.4.1; se agregan las columnas one-hot por variable de origen.",
            "comparison": "Las definiciones de importancia no comparten escala sustantiva; la suma por categorías y los predictores correlacionados condicionan la lectura.",
        },
        "importance_leaders": {},
    }
    for name in NAMES:
        frame = pd.read_csv(source / f"feature_importance_{name}.csv").head(5)
        summary["importance_leaders"][name] = [
            {"variable": row.variable, "label": LABELS.get(row.variable, row.variable),
             "importance": float(row.importance)} for row in frame.itertuples()
        ]
    (source / "model_interpretation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def create_model_figures(evaluation_dir: str | Path, destination: str | Path | None = None) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    source = Path(evaluation_dir)
    output = Path(destination) if destination is not None else source / "figures"
    metrics = json.loads((source / "model_metrics.json").read_text())
    if metrics.get("status") != "trained":
        raise ValueError("Se requieren métricas de modelos realmente entrenados.")
    for value in metrics["models"].values():
        if "holdout_curves" not in value:
            raise ValueError("Ejecuta model para generar las curvas agregadas de evaluación.")
    write_model_summary(source)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.titlesize": 12, "axes.labelsize": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    artifacts = []
    split = metrics["split"]

    # ROC y PR: valores exactos de las métricas en las leyendas; las curvas son
    # representaciones agregadas remuestreadas para no publicar scores de personas.
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.8))
    interactive = make_subplots(rows=1, cols=2, subplot_titles=("Curva ROC ponderada", "Precisión y recall ponderados"))
    for name, model in metrics["models"].items():
        curve = model["holdout_curves"]["weighted"]
        scores = model["holdout"]["weighted"]
        color = COLORS[name]
        roc_name = f'{NAMES[name]} AUC {scores["roc_auc"]:.3f}'
        pr_name = f'{NAMES[name]} AP {scores["average_precision"]:.3f}'
        axes[0].plot(curve["fpr"], curve["tpr"], color=color, lw=2, label=roc_name)
        axes[1].plot(curve["recall"], curve["precision"], color=color, lw=2, label=pr_name)
        interactive.add_trace(go.Scatter(x=curve["fpr"], y=curve["tpr"], mode="lines",
                                        name=roc_name, line={"color": color}), row=1, col=1)
        interactive.add_trace(go.Scatter(x=curve["recall"], y=curve["precision"], mode="lines",
                                        name=pr_name, line={"color": color}), row=1, col=2)
    prevalence = split["test_positive_prevalence_weighted"]
    axes[0].plot([0, 1], [0, 1], "--", color="#777777", lw=1, label="Referencia sin discriminación")
    axes[1].axhline(prevalence, color="#777777", ls="--", lw=1,
                    label=f"Referencia prevalencia {prevalence:.3f}")
    interactive.add_shape(type="line", x0=0, y0=0, x1=1, y1=1,
                          line={"color": "gray", "dash": "dash"}, row=1, col=1)
    interactive.add_shape(type="line", x0=0, y0=prevalence, x1=1, y1=prevalence,
                          line={"color": "gray", "dash": "dash"}, row=1, col=2)
    for ax, title, xlabel, ylabel in zip(axes,
            ["Curva ROC ponderada", "Precisión y recall ponderados"],
            ["Tasa de falsos positivos", "Recall o sensibilidad"],
            ["Sensibilidad", "Precisión"]):
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel, xlim=(0, 1), ylim=(0, 1.02))
        ax.grid(alpha=0.18); ax.legend(loc="lower right" if ax is axes[0] else "upper right", fontsize=8)
    fig.suptitle(f'Evaluación en reserva por UPM n = {split["n_test"]}', y=1.01)
    fig.text(.5, -.02, "EH2025 INE · No asistencia de 12 a 17 años · Curvas agregadas · AP y AUC calculadas antes del remuestreo",
             ha="center", fontsize=8)
    fig.tight_layout()
    png = output / "roc_precision_recall.png"; fig.savefig(png, dpi=180, bbox_inches="tight"); plt.close(fig)
    interactive.update_xaxes(title_text="Tasa de falsos positivos", range=[0, 1], row=1, col=1)
    interactive.update_yaxes(title_text="Sensibilidad", range=[0, 1], row=1, col=1)
    interactive.update_xaxes(title_text="Recall o sensibilidad", range=[0, 1], row=1, col=2)
    interactive.update_yaxes(title_text="Precisión", range=[0, 1], row=1, col=2)
    interactive.update_layout(template="plotly_white", height=520,
                              title=f'Evaluación en reserva por UPM n = {split["n_test"]}')
    html = output / "roc_precision_recall.html"; interactive.write_html(html, include_plotlyjs=True)
    artifacts.extend([str(png), str(html)])

    # Matrices con observaciones sin ponderar y sumas ponderadas de la reserva.
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 8.8))
    inter_cm = make_subplots(rows=2, cols=2, subplot_titles=[
        f"{NAMES[name]} {kind}" for name in NAMES for kind in ["sin ponderar", "suma de pesos"]])
    for row, name in enumerate(NAMES):
        for col, kind in enumerate(["unweighted", "weighted"]):
            matrix = np.asarray(metrics["models"][name]["holdout"][kind]["confusion_matrix"])
            ax = axes[row, col]
            ax.imshow(matrix, cmap="Blues", vmin=0)
            for (i, j), value in np.ndenumerate(matrix):
                text = f"{int(value):,}" if kind == "unweighted" else f"{value:,.1f}"
                ax.text(j, i, text, ha="center", va="center", fontsize=12,
                        color="white" if value > matrix.max()*.55 else "black")
            ax.set_xticks([0, 1], ["Asiste", "No asistencia"])
            ax.set_yticks([0, 1], ["Asiste", "No asistencia"])
            ax.set(xlabel="Predicción", ylabel="Condición observada",
                   title=NAMES[name] + (" sin ponderar" if kind == "unweighted" else " suma de pesos"))
            inter_cm.add_trace(go.Heatmap(z=matrix, x=["Asiste", "No asistencia"],
                y=["Asiste", "No asistencia"], text=matrix.round(1), texttemplate="%{text}",
                showscale=False, colorscale="Blues"), row=row+1, col=col+1)
    fig.suptitle("Matrices de confusión con umbral fijo 0.5", y=1.005)
    fig.text(.5, -.015, "Las sumas de pesos corresponden solo a la reserva y no representan el total nacional.", ha="center", fontsize=9)
    fig.tight_layout()
    png = output / "confusion_matrices.png"; fig.savefig(png, dpi=180, bbox_inches="tight"); plt.close(fig)
    inter_cm.update_layout(template="plotly_white", height=750, title="Matrices de confusión con umbral fijo 0.5")
    html = output / "confusion_matrices.html"; inter_cm.write_html(html, include_plotlyjs=True)
    artifacts.extend([str(png), str(html)])

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.3))
    inter_imp = make_subplots(rows=1, cols=2, subplot_titles=[NAMES[name] for name in NAMES], horizontal_spacing=.27)
    for i, name in enumerate(NAMES):
        frame = pd.read_csv(source / f"feature_importance_{name}.csv").sort_values("importance", ascending=True)
        labels = [LABELS.get(value, value) for value in frame["variable"]]
        axes[i].barh(labels, frame["importance"], color=COLORS[name])
        axes[i].set(title=NAMES[name], xlabel="Importancia nativa agregada")
        axes[i].grid(axis="x", alpha=.18)
        inter_imp.add_trace(go.Bar(x=frame["importance"], y=labels, orientation="h",
                                  marker_color=COLORS[name], showlegend=False), row=1, col=i+1)
    fig.suptitle("Importancia predictiva de las variables", y=1.015)
    fig.text(.5, -.03, "No expresa efectos causales. Las importancias nativas de cada modelo tienen definiciones distintas.", ha="center", fontsize=9)
    fig.tight_layout(w_pad=3)
    png = output / "feature_importances.png"; fig.savefig(png, dpi=180, bbox_inches="tight"); plt.close(fig)
    inter_imp.update_layout(template="plotly_white", height=600, title="Importancia predictiva de las variables",
                             margin={"l": 220, "r": 35, "t": 70, "b": 70})
    html = output / "feature_importances.html"; inter_imp.write_html(html, include_plotlyjs=True)
    artifacts.extend([str(png), str(html)])

    manifest = {"artifacts": artifacts, "source": "model_metrics.json e importancias agregadas",
                "individual_predictions_published": False}
    (output / "figures_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Figuras de evaluación desde resultados agregados")
    parser.add_argument("evaluation_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(create_model_figures(args.evaluation_dir, args.output_dir), ensure_ascii=False, indent=2))
