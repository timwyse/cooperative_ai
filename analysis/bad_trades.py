
import pandas as pd
import ast
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import bootstrap
from matplotlib.lines import Line2D

from format_results import format_data, MODEL_ORDER, BUCKET_ORDER, CONTRACT_ORDER, FULL_DF, DEFAULT_FONT_SIZE, OUTPUT_FOLDER

def plot_mean_metric_bar(
    df: pd.DataFrame,
    metric: str,
    x: str,
    hue: str | None = None,
    filters: list[tuple[str, list]] | None = None,
    display_filter: bool = True,
    order: list | None = None,
    hue_order: list | None = None,
    figsize=(12, 6),
    title: str | None = None,
    rotate_xticks=10,
    ylim=(0, 1),
    palette="Set2",
):
    data = df.copy()

    filter_text = ""
    if filters:
        filter_text = ';\n '.join([f"{col} in {allowed}" for col, allowed in filters])
        for col, allowed in filters:
            if col not in data.columns:
                raise ValueError(f"Filter column '{col}' not in df.columns")
            data = data[data[col].isin(allowed)]

    required = [x, metric] + ([hue] if hue else [])
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data = data.dropna(subset=required)
    if data.empty:
        raise ValueError("No data left after filtering/dropna.")

    group_cols = [x] + ([hue] if hue else [])
    grouped = (
        data.groupby(group_cols, observed=True)[metric]
            .agg(mean="mean", std="std", n="count")
            .reset_index()
    )
    grouped["sem"] = np.where(grouped["n"] > 1, grouped["std"] / np.sqrt(grouped["n"]), 0.0)

    x_levels = order if order is not None else list(pd.unique(grouped[x]))
    if hue:
        h_levels = hue_order if hue_order is not None else list(pd.unique(grouped[hue]))
    else:
        h_levels = [None]

    if hue:
        mean_mat = grouped.pivot(index=x, columns=hue, values="mean").reindex(index=x_levels, columns=h_levels)
        sem_mat = grouped.pivot(index=x, columns=hue, values="sem").reindex(index=x_levels, columns=h_levels)
        colors = sns.color_palette(palette, n_colors=len(h_levels))
    else:
        mean_mat = grouped.set_index(x)["mean"].reindex(x_levels).to_frame("mean")
        sem_mat = grouped.set_index(x)["sem"].reindex(x_levels).to_frame("sem")
        colors = sns.color_palette(palette, n_colors=1)

    fig, ax = plt.subplots(figsize=figsize)

    x_pos = np.arange(len(x_levels))
    if hue:
        width = 0.8 / max(len(h_levels), 1)
        offsets = (np.arange(len(h_levels)) - (len(h_levels) - 1) / 2) * width

        for j, h_val in enumerate(h_levels):
            y = mean_mat[h_val].to_numpy(dtype=float)
            yerr = sem_mat[h_val].to_numpy(dtype=float)

            ax.bar(
                x_pos + offsets[j],
                y,
                width=width,
                yerr=yerr,
                capsize=4,
                label=str(h_val),
                color=colors[j],
                alpha=0.9,
                edgecolor="black",
                linewidth=0.3,
            )
        ax.legend(title=hue, loc="best")
    else:
        y = mean_mat["mean"].to_numpy(dtype=float)
        yerr = sem_mat["sem"].to_numpy(dtype=float)

        # one color per x-level
        bar_colors = sns.color_palette(palette, n_colors=len(x_levels))

        ax.bar(
            x_pos,
            y,
            width=0.7,
            yerr=yerr,
            capsize=4,
            color=bar_colors,
            alpha=0.9,
            edgecolor="black",
            linewidth=0.3,
        )

    ax.set_xticks(x_pos)
    ax.set_xticklabels([str(v) for v in x_levels], rotation=rotate_xticks, ha="right")
    # ax.set_xlabel(x, fontsize=DEFAULT_FONT_SIZE)
    ax.set_ylabel(f"Mean {metric.replace('_',' ')}")
    ax.set_title(title if title else None)

    if ylim is not None:
        ax.set_ylim(*ylim)

    plt.savefig(f"{OUTPUT_FOLDER}/mean_{metric.replace(' ', '_').lower()}_by_{x.lower()}.pdf", format="pdf", bbox_inches="tight")
    fig.tight_layout()
    

    return grouped

if __name__ == "__main__":

    df = format_data(FULL_DF, p4p=False)

    core_metrics = [
    {'df': df,
        'metric': 'Bad Trade',
                    'x': 'Contract Type',
                    'hue': 'Model',
                    'order': None,
                    'hue_order': MODEL_ORDER,
                    'filters':[("Pay4Partner", [False]), 
                    # ('Contract Type', ['Strict Tile', 'Natural Language Tile']),
                    ('Bucket', ['Independent', 'Mutually Dependent', 'Asymmetric'])],
    },
    ]

    ##################### FIG 15 ####################
    for metric_cfg in core_metrics:
        print(f"Plotting metric: {metric_cfg['metric']}")
        plot_mean_metric_bar(
            df=metric_cfg['df'],
            metric=metric_cfg['metric'],
            x=metric_cfg['x'],
            hue=metric_cfg.get('hue', None),
            filters=metric_cfg.get('filters', None),
            display_filter=metric_cfg.get('display_filter', True),
            order=metric_cfg.get('order', None),
            hue_order=metric_cfg.get('hue_order', None),
            ylim=None
            
        )