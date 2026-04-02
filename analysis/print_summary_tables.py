
import pandas as pd
import ast
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import bootstrap
from matplotlib.lines import Line2D

from format_results import format_data, MODEL_ORDER, BUCKET_ORDER, CONTRACT_ORDER, FULL_DF, DEFAULT_FONT_SIZE, OUTPUT_FOLDER

def print_model_metric_summaries(
    df: pd.DataFrame,
    metrics: list[str],
    contract_types: list[str] | None = None,
    buckets: list[str] | None = None,
    model_col: str = "Model",
    output_latex: bool = True,
    latex_metric_names: dict[str, str] | None = None,
    latex_decimal_places: dict[str, int] | None = None,
    asymmetric_only_metrics: list[str] | None = None,
    show_overall_mean: bool = True,
    ci: float = 0.95,
    appendix: bool = False,
):
    """
    Print metric summaries per model, and optionally output a LaTeX table.

    Args:
        metrics: All metrics to include in the table.
        asymmetric_only_metrics: Metrics that should only be computed on Asymmetric boards.
        latex_metric_names: Optional rename mapping for LaTeX headers.
        latex_decimal_places: Optional per-metric decimal places.
        show_overall_mean: If True, add an "Overall" row at the bottom (mean across all data).
        ci: Confidence level (default 0.95 for 95% CI).
        appendix: If True, only show means (no ± CI) in both console and LaTeX output.
    """
    from scipy import stats

    if latex_metric_names is None:
        latex_metric_names = {}
    if latex_decimal_places is None:
        latex_decimal_places = {}
    if asymmetric_only_metrics is None:
        asymmetric_only_metrics = []

    data = df.copy()
    
    if contract_types is not None:
        data = data[data["Contract Type"].isin(contract_types)]
    if buckets is not None:
        data = data[data["Bucket"].isin(buckets)]

    def _ci_half_width(group, col, ci_level):
        """Compute half-width of the CI: t * std / sqrt(n)."""
        vals = group[col].dropna()
        n = len(vals)
        if n < 2:
            return float("nan")
        sem = vals.std() / np.sqrt(n)
        t_crit = stats.t.ppf((1 + ci_level) / 2, df=n - 1)
        return t_crit * sem

    def _fmt_val(mean, hw, dp, bold=False, latex=True):
        """Format a value as mean ± ci or just mean depending on appendix flag."""
        if latex:
            if appendix:
                inner = f"{mean:.{dp}f}"
            else:
                inner = f"{mean:.{dp}f} \\pm {hw:.{dp}f}"
            if bold:
                return f"$\\mathbf{{{inner}}}$"
            else:
                return f"${inner}$"
        else:
            if appendix:
                return f"{mean:.{dp}f}"
            else:
                return f"{mean:.{dp}f} ± {hw:.{dp}f}"

    # Split metrics into normal and asymmetric-only
    normal_metrics = [m for m in metrics if m not in asymmetric_only_metrics]
    asym_metrics = [m for m in metrics if m in asymmetric_only_metrics]

    # Compute normal metrics on full data
    results = {}
    if normal_metrics:
        for model, group in data.groupby(model_col):
            results[model] = {}
            for m in normal_metrics:
                results[model][m] = (
                    group[m].mean(),
                    _ci_half_width(group, m, ci),
                )

    # Compute asymmetric-only metrics on Asymmetric subset
    if asym_metrics:
        asym_data = data[data["Bucket"] == "Asymmetric"]
        if not asym_data.empty:
            for model, group in asym_data.groupby(model_col):
                if model not in results:
                    results[model] = {}
                for m in asym_metrics:
                    results[model][m] = (
                        group[m].mean(),
                        _ci_half_width(group, m, ci),
                    )
        else:
            print("Warning: No Asymmetric data found for asymmetric-only metrics.")
            for model in results:
                for m in asym_metrics:
                    results[model][m] = (float("nan"), float("nan"))

    # Compute overall mean across all data
    overall = {}
    if show_overall_mean:
        if normal_metrics:
            for m in normal_metrics:
                overall[m] = (
                    data[m].mean(),
                    _ci_half_width(data, m, ci),
                )
        if asym_metrics:
            asym_data = data[data["Bucket"] == "Asymmetric"]
            for m in asym_metrics:
                if not asym_data.empty:
                    overall[m] = (
                        asym_data[m].mean(),
                        _ci_half_width(asym_data, m, ci),
                    )
                else:
                    overall[m] = (float("nan"), float("nan"))

    # # --- Print to console ---
    # for model in sorted(results.keys()):
    #     print(f"\n{model}")
    #     for m in metrics:
    #         if m in results[model]:
    #             mean, hw = results[model][m]
    #             dp = latex_decimal_places.get(m, 3)
    #             print(f"  {m}: {_fmt_val(mean, hw, dp, latex=False)}")

    # if show_overall_mean:
    #     print(f"\nMean (all models)")
    #     for m in metrics:
    #         if m in overall:
    #             mean, hw = overall[m]
    #             dp = latex_decimal_places.get(m, 3)
    #             print(f"  {m}: {_fmt_val(mean, hw, dp, latex=False)}")

    # --- Output LaTeX table ---
    if output_latex:
        header_names = [latex_metric_names.get(m, m) for m in metrics]
        header = "\\textbf{Model}\n"
        for name in header_names:
            header += f"& \\textbf{{{name}}}\n"
        header += "\\\\\n\\midrule"

        rows = []
        for model in sorted(results.keys()):
            row = f"{model}\n"
            for m in metrics:
                if m in results[model]:
                    mean, hw = results[model][m]
                    dp = latex_decimal_places.get(m, 3)
                    row += f"& {_fmt_val(mean, hw, dp, bold=False, latex=True)}\n"
                else:
                    row += "& ---\n"
            row += "\\\\"
            rows.append(row)

        # Overall row
        if show_overall_mean:
            overall_row = "\\midrule\n\\textbf{Mean (all models)}\n"
            for m in metrics:
                if m in overall:
                    mean, hw = overall[m]
                    dp = latex_decimal_places.get(m, 3)
                    overall_row += f"& {_fmt_val(mean, hw, dp, bold=True, latex=True)}\n"
                else:
                    overall_row += "& ---\n"
            overall_row += "\\\\"
            rows.append(overall_row)

        latex = header + "\n" + "\n\n".join(rows)

        ci_pct = int(ci * 100)
        print(f"\n\n% ---- LaTeX Table ({ci_pct}% CI) ----")
        print("\\begin{table*}[t]")
        print("\\centering")
        print("\\begin{small}")
        print("\\begin{tabular}{l" + "c" * len(metrics) + "}")
        print("\\toprule")
        print(latex)
        print("\\bottomrule")
        print("\\end{tabular}")
        print("\\end{small}")
        print(f"\\caption{{Summary table for {contract_types[0]}; }}")
        print("\\label{tab:}")
        print("\\end{table*}")
        print(f"% ---- End LaTeX Table ({ci_pct}% CI) ----\n")


if __name__ == "__main__":
    
    metrics=[
            "Normalized Joint Reward",
            "Gini",
            "Both Finished",
            "Both Beat Baseline",
            "total_trade_volume",
            "Defection Rate",
            "contract_accepted"
        ]
    df_p4p = format_data(FULL_DF, p4p=True)

    for contract in CONTRACT_ORDER:
        print(f"\n\n=== Contract: {contract} ===")
        print_model_metric_summaries(
            df=df_p4p[df_p4p["Contract Type"] == contract],
            metrics=metrics,
            model_col="Model",
            output_latex=True,
            latex_metric_names={
                "Normalized Joint Reward": "Norm. Joint Reward",
                "Gini": "Gini",
                "Both Finished": "Both Finished",
                "Both Beat Baseline": "Both Beat Baseline",
                "total_trade_volume": "Total Trade Vol.",
                "Defection Rate": "Defection Rate",
                "contract_accepted": "Contract Accepted",
            },
            latex_decimal_places={
                "Normalized Joint Reward": 3,
                "Gini": 3,
                "Both Finished": 2,
                "Both Beat Baseline": 2,
                "total_trade_volume": 1,
                "Defection Rate": 3,
                "contract_accepted": 3,
            },
            asymmetric_only_metrics=["Defection Rate", "contract_accepted"],
            show_overall_mean=True,
            ci=0.95,
            appendix=False,
        )

    df_reg_trading = format_data(FULL_DF, p4p=False)
    for contract in CONTRACT_ORDER:
        print(f"\n\n=== Contract: {contract} (Regular Trading) ===")
        print_model_metric_summaries(
            df=df_reg_trading[df_reg_trading["Contract Type"] == contract],
            metrics=metrics,
            model_col="Model",
            output_latex=True,
            latex_metric_names={
                "Normalized Joint Reward": "Norm. Joint Reward",
                "Gini": "Gini",
                "Both Finished": "Both Finished",
                "Both Beat Baseline": "Both Beat Baseline",
                "total_trade_volume": "Total Trade Vol.",
                "Defection Rate": "Defection Rate",
                "contract_accepted": "Contract Accepted",
            },
            latex_decimal_places={
                "Normalized Joint Reward": 3,
                "Gini": 3,
                "Both Finished": 2,
                "Both Beat Baseline": 2,
                "total_trade_volume": 1,
                "Defection Rate": 3,
                "contract_accepted": 3,
            },
            asymmetric_only_metrics=["Defection Rate", "contract_accepted"],
            show_overall_mean=True,
            ci=0.95,
            appendix=False,
        )