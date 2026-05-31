
import argparse
import os
import pandas as pd
import ast
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import bootstrap
from matplotlib.lines import Line2D

from format_results import format_data, MODEL_ORDER, BUCKET_ORDER, CONTRACT_ORDER, FULL_DF, DEFAULT_FONT_SIZE, OUTPUT_FOLDER

def plot_panels_boards_overlaid(
    df: pd.DataFrame,
    board_types: list[str],
    contract_order: list[str],
    output_folder: str,
    metrics: list[str] | str = "Both Finished",
    figsize: tuple[float, float] | None = None,
    rotate_xticks: int = 0,
    abbreviate_x_labels: bool = True,
    metric_name_mapping: dict[str, str] | None = None,
):
    """
    One subplot per metric. Accepts a single string or a list of strings.
    """
    from matplotlib.patches import FancyBboxPatch

    if isinstance(metrics, str):
        metrics = [metrics]

    n_panels = len(metrics)

    # Default short x-axis labels
    if abbreviate_x_labels:
        x_labels = {
            "No Contract": "NC",
            "Prog-Points": "PP",
            "NL-Trading": "NLT",
            "Prog-Trading": "PT",
        }
    else:
        x_labels = {ct: ct for ct in contract_order}

    RT = df.copy()
    RT = RT[(RT["Board Type"].isin(board_types))].copy()
    RT["Contract Type"] = pd.Categorical(RT["Contract Type"], categories=contract_order, ordered=True)

    # Ensure all metrics exist
    for m in metrics:
        if m not in RT.columns:
            if ("Reward P-Red" in RT.columns) and ("Reward P-Blue" in RT.columns):
                s = RT["Reward P-Red"] + RT["Reward P-Blue"]
                RT[m] = np.where(s > 0, np.abs(RT["Reward P-Red"] - RT["Reward P-Blue"]) / s, 0.0)
            else:
                raise ValueError(f"Missing '{m}' and cannot compute it (need Reward P-Red/Reward P-Blue).")

    # Bucket colors
    default_bucket_colors = {
        "Independent": "tab:green",
        "Mutually Dependent": "tab:purple",
        "Asymmetric": "tab:red",
    }
    bucket_to_color = {b: default_bucket_colors.get(b, "tab:gray") for b in board_types}

    models = sorted(RT["Model"].dropna().unique().tolist())
    model_markers = ['^', 's', 'D', 'P', 'X', '*', 'v', '<', '>', 'H']
    if len(models) > len(model_markers):
        raise ValueError(f"Not enough marker shapes for {len(models)} models; add more to model_markers.")
    model_to_marker = {m: model_markers[i] for i, m in enumerate(models)}

    xpos = {ct: i for i, ct in enumerate(contract_order)}

    long = RT.melt(
        id_vars=["Board Type", "Contract Type", "Model", "Grid ID"],
        value_vars=metrics,
        var_name="Metric",
        value_name="Value",
    )

    per_grid_model = (
        long
        .groupby(["Board Type", "Contract Type", "Model", "Metric", "Grid ID"], as_index=False, observed=True)["Value"]
        .mean()
    )

    model_means = (
        per_grid_model
        .groupby(["Board Type", "Contract Type", "Model", "Metric"], as_index=False, observed=True)["Value"]
        .mean()
        .rename(columns={"Value": "Score"})
    )

    bucket_stats = (
        long
        .groupby(["Board Type", "Contract Type", "Metric"], observed=True)
        .agg(mean_score=("Value", "mean"), sd=("Value", "std"), n=("Value", "count"))
        .reset_index()
    )
    bucket_stats["sem"] = bucket_stats["sd"] / np.sqrt(bucket_stats["n"])
    bucket_stats["ci95"] = 1.96 * bucket_stats["sem"]
    bucket_stats.loc[bucket_stats["n"] <= 1, "ci95"] = 0.0

    bucket_span = 0.22
    bucket_offsets = [0.0] if len(board_types) == 1 else list(np.linspace(-bucket_span, bucket_span, num=len(board_types)))
    bucket_to_offset = {b: bucket_offsets[i] for i, b in enumerate(board_types)}

    model_span = 0.08
    model_offsets = [0.0] if len(models) == 1 else list(np.linspace(-model_span, model_span, num=len(models)))
    model_to_offset = {m: model_offsets[i] for i, m in enumerate(models)}

    # Default figsize scales with number of panels
    if figsize is None:
        figsize = (5 * n_panels + 2, 6)

    fig, axes = plt.subplots(nrows=1, ncols=n_panels, figsize=figsize, sharex=True, squeeze=False)
    axes = axes[0]

    for panel_idx, metric in enumerate(metrics):
        ax = axes[panel_idx]

        mm = model_means[model_means["Metric"] == metric]
        for b in board_types:
            mmb = mm[mm["Board Type"] == b]
            if mmb.empty:
                continue
            for m in models:
                d = mmb[mmb["Model"] == m]
                if d.empty:
                    continue
                xs = (
                    d["Contract Type"].map(xpos).to_numpy()
                    + bucket_to_offset[b]
                    + model_to_offset[m]
                )
                ys = d["Score"].to_numpy()
                ax.scatter(
                    xs, ys, s=55,
                    marker=model_to_marker[m],
                    color=bucket_to_color[b],
                    alpha=0.4, edgecolors="k", linewidths=0.25, zorder=2,
                )

        bs = bucket_stats[bucket_stats["Metric"] == metric]
        for b in board_types:
            d = bs[bs["Board Type"] == b]
            if d.empty:
                continue
            xs = d["Contract Type"].map(xpos).to_numpy() + bucket_to_offset[b]
            ys = d["mean_score"].to_numpy()
            yerr = np.nan_to_num(d["ci95"].to_numpy(), nan=0.0)
            ax.scatter(
                xs, ys, s=140, marker="o",
                color=bucket_to_color[b], alpha=1.0,
                edgecolors="k", linewidths=1.0, zorder=6,
            )
            ax.errorbar(
                xs, ys, yerr=yerr, fmt="none",
                ecolor=bucket_to_color[b], elinewidth=1.0,
                capsize=4, capthick=1.6, alpha=0.95, zorder=10,
            )

        # Metric name as title above the panel instead of y-axis label
        if metric_name_mapping and metric in metric_name_mapping:
            ax.set_title(metric_name_mapping[metric], fontsize=1.15*DEFAULT_FONT_SIZE, fontweight="bold", pad=8)
        else:
            ax.set_title(metric, fontsize=1.15*DEFAULT_FONT_SIZE, fontweight="bold", pad=8)
        ax.set_ylabel("")  # remove y-axis label
        ax.tick_params(axis="y", labelsize=0.85 * DEFAULT_FONT_SIZE)
        # ax.set_ylim(-0.1, 1)
        # if panel_idx > 0:
        #     ax.set_yticklabels([])

        ax.grid(axis="y", alpha=0.15)
        ax.set_xticks(range(len(contract_order)))
        ax.set_xticklabels(
            [x_labels.get(ct, ct) for ct in contract_order],
            rotation=rotate_xticks,
            ha="center",
            fontsize=DEFAULT_FONT_SIZE,
        )

    # --- Legend ---
    x_label_handles = [
        Line2D([0], [0], marker="None", linestyle="None",
               label=f"{x_labels.get(ct, ct)} = {ct}")
        for ct in (contract_order)
    ]

    bucket_handles = [
        Line2D([0], [0], marker="o", linestyle="None",
               markerfacecolor=bucket_to_color[b], markeredgecolor="k",
               markersize=9, label=b)
        for b in board_types
    ]
    model_handles = [
        Line2D([0], [0], marker=model_to_marker[m], linestyle="None",
               markerfacecolor="0.65", markeredgecolor="k",
               markersize=8, label=m)
        for m in models
    ]

    fig.subplots_adjust(bottom=0.28, left=0.06, right=0.98, wspace=0.25)

    fig.canvas.draw()

    
    if abbreviate_x_labels:
    # Contract abbreviations legend (top row)
        leg_abbrev = fig.legend(
            handles=x_label_handles,
            loc="lower center",
            bbox_to_anchor=(0.54, 0.11),
            ncol=len(x_label_handles),
            fontsize=DEFAULT_FONT_SIZE,
            frameon=False,
            handletextpad=0.0,
            handlelength=0.0,
            columnspacing=1.5,
        )
        fig.canvas.draw()
        bb = leg_abbrev.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
        fig.text(
            bb.x0 - 0.01, bb.y0 + bb.height / 2,
            "Contracts:",
            fontsize=DEFAULT_FONT_SIZE, fontweight="bold",
            ha="right", va="center", transform=fig.transFigure,
        )

    # Board type legend (middle row)
    leg_bucket = fig.legend(
        handles=bucket_handles,
        loc="lower center",
        bbox_to_anchor=(0.54, 0.05),
        ncol=len(bucket_handles),
        fontsize=DEFAULT_FONT_SIZE,
        frameon=False,
        handletextpad=0.4,
        columnspacing=1.0,
    )
    fig.canvas.draw()
    bb = leg_bucket.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    fig.text(
        bb.x0 - 0.01, bb.y0 + bb.height / 2,
        "Board Type:",
        fontsize=DEFAULT_FONT_SIZE, fontweight="bold",
        ha="right", va="center", transform=fig.transFigure,
    )

    # Model legend (bottom row)
    leg_model = fig.legend(
        handles=model_handles,
        loc="lower center",
        bbox_to_anchor=(0.54, 0.0),
        ncol=len(model_handles),
        fontsize=DEFAULT_FONT_SIZE,
        frameon=False,
        handletextpad=0.4,
        columnspacing=1.0,
    )
    fig.canvas.draw()
    bb = leg_model.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    fig.text(
        bb.x0 - 0.01, bb.y0 + bb.height / 2,
        "Model:",
        fontsize=DEFAULT_FONT_SIZE, fontweight="bold",
        ha="right", va="center", transform=fig.transFigure,
    )

    # Enclosing box around all three legend rows
    if abbreviate_x_labels:
        fig.add_artist(leg_abbrev)
    fig.add_artist(leg_bucket)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    if abbreviate_x_labels:
        bb1 = leg_abbrev.get_window_extent(renderer).transformed(fig.transFigure.inverted())
        bb1_x0 = bb1.x0
        bb1_y0 = bb1.y0
        bb1_x1 = bb1.x1
        bb1_y1 = bb1.y1
    else:
        bb1_x0 = float('inf')
        bb1_y0 = float('inf')
        bb1_x1 = float('-inf')
        bb1_y1 = float('-inf')
    
    bb2 = leg_bucket.get_window_extent(renderer).transformed(fig.transFigure.inverted())
    bb3 = leg_model.get_window_extent(renderer).transformed(fig.transFigure.inverted())
    

    pad = 0.012
    x0 = min(bb1_x0, bb2.x0, bb3.x0) - 0.08
    y0 = min(bb1_y0, bb2.y0, bb3.y0)
    x1 = max(bb1_x1, bb2.x1, bb3.x1)
    y1 = max(bb1_y1, bb2.y1, bb3.y1)

    box = FancyBboxPatch(
        (x0 - pad, y0 - pad),
        (x1 - x0) + 2 * pad,
        (y1 - y0) + 2 * pad,
        boxstyle="round,pad=0.001",
        facecolor="white",
        edgecolor="0.7",
        linewidth=1.0,
        transform=fig.transFigure,
        zorder=0,
    )
    fig.patches.append(box)

    p4p_bool = df['Pay4Partner'].iloc[0]
    p4p = 'p4p' if p4p_bool else 'regular_trading'
    metrics_str = "_".join(m.replace(" ", "_") for m in metrics)
    os.makedirs(output_folder, exist_ok=True)
    output_path = f"{output_folder}/{p4p}_{metrics_str}_panels.pdf"
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    print(f"Saved figure to {output_path}")
    # plt.show()



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", default=None, help="Path to CSV to be formatted by format_data (default: use FULL_DF)")
    parser.add_argument("--output-folder", default=OUTPUT_FOLDER, help=f"Output folder for figures (default: {OUTPUT_FOLDER})")
    args = parser.parse_args()

    input_df = FULL_DF if args.input_csv is None else pd.read_csv(args.input_csv)

    df = format_data(input_df, p4p=True)

    ######################### FIG 4 ####################
    plot_panels_boards_overlaid(
        df=df,
        board_types=BUCKET_ORDER,
        contract_order=CONTRACT_ORDER,
        output_folder=args.output_folder,
        metrics=["Normalized Joint Reward", "Gini", "Both Finished", 'Both Beat Baseline'],
        figsize=(18, 6),
    )



    ##################### FIG 6 ####################
    plot_panels_boards_overlaid(
        df=df,
        board_types=["Independent", "Mutually Dependent", "Asymmetric"],
        contract_order=['Prog-Points', 'Prog-Trading'],
        output_folder=args.output_folder,
        metrics=['contract_accepted', 'contract_negotiaion_length', 'Contract Gini', 'Contract Even Split', 'Contract Winner Take All'],
        figsize=(18, 6),
            metric_name_mapping={
                'contract_accepted': 'Acceptance Rate',
                'contract_negotiaion_length': 'Negotiation Length',
                'Contract Gini': 'Contract Gini',
                'Contract Even Split': 'Even Split Rate',
                'Contract Winner Take All': 'Winner Takes All Rate',
            }
    )



    ##################### FIG 9 ####################
    fma_df = df[df['Contract Type'].isin(['Prog-Points','Prog-Trading'])].copy()

    fma_df['Proportion to First Mover'] = np.where(
        fma_df['Contract Type'] == 'Prog-Points',
        fma_df['contract_for_finishing_points_proportion_P-Red'],
        fma_df['strict_contract_tile_proportion_P-Red']
    )

    plot_panels_boards_overlaid(
        df=fma_df,
        board_types=["Independent", "Mutually Dependent", "Asymmetric"],
        contract_order=['Prog-Points','Prog-Trading'],
        metrics=['Proportion to First Mover'],
        output_folder=args.output_folder,
        figsize=(18, 6),
    )


    ##################### FIG 10 ####################
    plot_panels_boards_overlaid(
        df=df,
        board_types=["Independent", "Mutually Dependent", "Asymmetric"],
        contract_order=CONTRACT_ORDER,
        output_folder=args.output_folder,
        metrics=["Defection Volume", 'Total P4P Promises Kept'],#,'Defection Rate'],
        figsize=(18, 6),
    )



    reg_trading_df = format_data(input_df, p4p=False)

    ######################### FIG 14 ####################
    plot_panels_boards_overlaid(
        df=reg_trading_df,
        board_types=BUCKET_ORDER,
        contract_order=CONTRACT_ORDER,
        output_folder=args.output_folder,
        metrics=["Normalized Joint Reward", "Gini", "Both Finished", 'Both Beat Baseline'],
        figsize=(18, 6),
    )