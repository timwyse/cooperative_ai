import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from matplotlib.colors import Normalize


from format_results import format_data, MODEL_ORDER, BUCKET_ORDER, CONTRACT_ORDER, FULL_DF, DEFAULT_FONT_SIZE, OUTPUT_FOLDER

def plot_grid_contract_heatmap(
    df: pd.DataFrame,
    metric: str,
    buckets: list[str] | None = None,
    contract_order: list[str] | None = None,
    agg: str = "mean",
    cmap: str = "RdYlGn",
    figsize: tuple[float, float] | None = None,
    show_grid_labels: bool = True,
    grid_label_every: int = 5,
    show_contract_labels: bool = True,
    robust: bool = False,
    vmin: float | None = 0.0,
    vmax: float | None = 1.0,
    title: str | None = None,
    bucket_label_fontsize: int = 16,
    col_width: float = 2.5,
    row_height: float = 0.12,
    grid_linewidth: float = 0.4,
    grid_linecolor: str = "0.4",
    output_folder: str = "analysis/figures",
    n_cols: int = 1,
):
    """
    Heatmap of metric per (Grid ID, Contract Type).

    Args:
        n_cols: Number of heatmap columns. Buckets are distributed across columns
                in order. e.g. with 3 buckets and n_cols=2:
                  col 0: bucket 0, bucket 1 (stacked)
                  col 1: bucket 2
    """
    data = df.copy()

    if buckets is not None:
        data = data[data["Bucket"].isin(buckets)]


    required = ["Remapped Grid ID", "Bucket", "Contract Type", metric]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    grouped = (
        data
        .groupby(["Bucket", "Remapped Grid ID", "Contract Type"], observed=True)[metric]
        .agg(agg)
        .reset_index()
    )

    if contract_order is None:
        contract_order = sorted(grouped["Contract Type"].dropna().unique().tolist())
    if buckets is None:
        buckets = ["Independent", "Mutually Dependent", "Asymmetric"]

    bucket_mats = {}
    for b in buckets:
        bdata = grouped[grouped["Bucket"] == b]
        if bdata.empty:
            continue
        mat = (
            bdata
            .pivot(index="Remapped Grid ID", columns="Contract Type", values=metric)
            .reindex(columns=contract_order)
            .sort_index()
        )
        bucket_mats[b] = mat

    if not bucket_mats:
        raise ValueError("No data for any bucket.")

    active_buckets = [b for b in buckets if b in bucket_mats]
    n_contracts = len(contract_order)

    # Distribute buckets across columns in order
    # e.g. 3 buckets, 2 cols → col0 gets 2, col1 gets 1
    buckets_per_col = [[] for _ in range(n_cols)]
    for i, b in enumerate(active_buckets):
        col_idx = min(i * n_cols // len(active_buckets), n_cols - 1)
        buckets_per_col[col_idx].append(b)

    # Or simpler: fill columns greedily by row count to balance heights
    # Actually just split: first (n-1) cols get ceil, last gets remainder
    # Simplest: user gives n_cols, we distribute evenly
    per_col = len(active_buckets) // n_cols
    remainder = len(active_buckets) % n_cols
    buckets_per_col = []
    idx = 0
    for c in range(n_cols):
        count = per_col + (1 if c < remainder else 0)
        buckets_per_col.append(active_buckets[idx:idx + count])
        idx += count

    # For each column, vertically concatenate the bucket matrices
    # Keep track of where each bucket starts/ends for labeling
    col_data = []  # list of (combined_mat, bucket_boundaries)
    max_rows = 0
    for col_buckets in buckets_per_col:
        mats = []
        boundaries = []  # (start_row, end_row, bucket_name)
        row_offset = 0
        for b in col_buckets:
            mat = bucket_mats[b]
            nr = mat.shape[0]
            boundaries.append((row_offset, row_offset + nr, b))
            mats.append(mat)
            row_offset += nr
        combined = pd.concat(mats, axis=0)
        col_data.append((combined, boundaries))
        max_rows = max(max_rows, combined.shape[0])

    # Figure size
    if figsize is None:
        width = col_width * n_contracts * n_cols + 3.0
        height = row_height * max_rows + 2.0
        figsize = (width, height)

    fig = plt.figure(figsize=figsize)

    # Outer gridspec: one column per heatmap + spacers
    width_ratios = []
    col_map = []  # index into col_data or None for spacer
    for i in range(n_cols):
        if i > 0:
            width_ratios.append(0.15)
            col_map.append(None)
        width_ratios.append(n_contracts)
        col_map.append(i)

    outer_gs = gridspec.GridSpec(
        nrows=1,
        ncols=len(width_ratios),
        figure=fig,
        width_ratios=width_ratios,
        wspace=0.12,
    )

    norm = Normalize(vmin=vmin, vmax=vmax)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    heat_axes = []

    for gs_col, data_idx in enumerate(col_map):
        if data_idx is None:
            continue

        combined_mat, boundaries = col_data[data_idx]
        ax = fig.add_subplot(outer_gs[0, gs_col])

        sns.heatmap(
            combined_mat.to_numpy(),
            ax=ax,
            cmap=cmap,
            robust=robust,
            vmin=vmin,
            vmax=vmax,
            cbar=False,
            linewidths=grid_linewidth,
            linecolor=grid_linecolor,
        )

        # Draw a thicker horizontal line between buckets
        for start, end, bname in boundaries[1:]:
            ax.axhline(y=start, color="black", linewidth=2.0)

        # Y-axis: grid IDs
        if show_grid_labels:
            tick_positions = []
            tick_labels = []
            for i, gid in enumerate(combined_mat.index):
                if i % grid_label_every == 0:
                    tick_positions.append(i + 0.5)
                    tick_labels.append(str(gid))
            ax.set_yticks(tick_positions)
            ax.set_yticklabels(tick_labels, rotation=0, fontsize=16)
        else:
            ax.set_yticks([])
        ax.tick_params(axis="y", length=0)
        ax.set_ylabel("")

        # Bucket labels on the left margin
        for start, end, bname in boundaries:
            mid_y = (start + end) / 2.0
            # Place text to the left of the axes
            ax.text(
                -0.05, 1.0 - mid_y / combined_mat.shape[0],
                bname,
                ha="right", va="center",
                fontsize=bucket_label_fontsize,
                fontweight="bold",
                rotation=90,
                transform=ax.transAxes,
            )

        # X-axis
        if show_contract_labels:
            ax.set_xticks(np.arange(n_contracts) + 0.5)
            ax.set_xticklabels(
                contract_order, rotation=0, ha="center",
                fontsize=16, fontweight="bold",
            )
        else:
            ax.set_xticks([])
        ax.set_xlabel("")

        heat_axes.append(ax)
    for ax in heat_axes:
        ax.text(
            -0.05, 1.02,
            "Board ID",
            ha="left",
            va="bottom",
            fontsize=16,
            fontstyle="italic",
            transform=ax.transAxes,
        )
    
    # Shared colorbar
    cbar = fig.colorbar(sm, ax=heat_axes, shrink=0.95, pad=0.03, aspect=40)
    cbar.set_label("")
    cbar.ax.tick_params(labelsize=14)

    if title:
        fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)

    p4p_bool = df['Pay4Partner'].iloc[0] 
    p4p_str = 'p4p' if p4p_bool else 'regular_trading'
    name = f'{p4p_str}_heatmap_for_{metric.replace(" ", "_")}'
    output_path = f"{output_folder}/{name}.pdf"
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="pdf", bbox_inches="tight")
    print(f"Saved figure to {output_path}")



if __name__ == "__main__":
    
    ########################## FIG 5 ####################
    df = format_data(FULL_DF, p4p=True)
    plot_grid_contract_heatmap(
        df=df,
        metric="Both Finished",
        buckets=["Independent", "Mutually Dependent", "Asymmetric"],
        contract_order=CONTRACT_ORDER,
        cmap="RdYlGn",
        vmin=0.0,
        vmax=1.0,
        show_grid_labels=True,
        grid_label_every=5,
        show_contract_labels=True,
        col_width=2.5,
        row_height=0.12,
        grid_linewidth=0.4,
        grid_linecolor="0.4",
        figsize=(24, 8),
        n_cols=2,
    )
