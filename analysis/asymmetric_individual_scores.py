
import pandas as pd
import ast
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import bootstrap
from matplotlib.lines import Line2D

from format_results import format_data, MODEL_ORDER, BUCKET_ORDER, CONTRACT_ORDER, FULL_DF, DEFAULT_FONT_SIZE, OUTPUT_FOLDER

def graph_per_player_points(df):
    from matplotlib.patches import FancyBboxPatch

    RT = df.copy()

    bucket = 'Asymmetric'
    p4p = True
    subset = RT[(RT['Bucket'] == bucket) & (RT['Pay4Partner'] == p4p)].copy()

    # Contract order
    order = CONTRACT_ORDER
    subset['Contract Type'] = pd.Categorical(subset['Contract Type'], categories=order, ordered=True)

    # Long format
    df_long = subset.melt(
        id_vars=['Contract Type', 'Model'],
        value_vars=['Reward P-Red', 'Reward P-Blue'],
        var_name='Player',
        value_name='Reward',
    )
    df_long['Player'] = df_long['Player'].map({'Reward P-Red': 'P-Red', 'Reward P-Blue': 'P-Blue'})
    player_order = ['P-Red', 'P-Blue']

    # Collapse to ONE point per (Contract, Model, Player)
    model_means = (
        df_long
        .groupby(['Contract Type', 'Model', 'Player'], as_index=False, observed=True)['Reward']
        .mean()
    )
    model_means['Player'] = pd.Categorical(model_means['Player'], categories=player_order, ordered=True)
    model_means = model_means.sort_values(['Contract Type', 'Model', 'Player'])

    # Averages across all models (per contract, per player)
    avg_long = (
        model_means
        .groupby(['Contract Type', 'Player'], as_index=False, observed=True)['Reward']
        .mean()
    )
    avg_long['Player'] = pd.Categorical(avg_long['Player'], categories=player_order, ordered=True)
    avg_long = avg_long.sort_values(['Contract Type', 'Player'])

    avg_stats = (
        df_long
        .groupby(['Contract Type', 'Player'], observed=True)
        .agg(
            mean_score=('Reward', 'mean'),
            sd=('Reward', 'std'),
            n=('Reward', 'count'),
        )
        .reset_index()
    )
    avg_stats['sem'] = avg_stats['sd'] / np.sqrt(avg_stats['n'])
    avg_stats['Player'] = pd.Categorical(avg_stats['Player'], categories=player_order, ordered=True)
    avg_stats['ci95'] = 1.96 * avg_stats['sem']
    avg_stats.loc[avg_stats['n'] <= 1, 'ci95'] = 0.0
    avg_stats = avg_stats.sort_values(['Contract Type', 'Player'])

    # Baselines
    baseline_p0 = subset['Non-Cooperative Baseline P-Red'].mean()
    baseline_p1 = subset['Non-Cooperative Baseline P-Blue'].mean()

    # Models + distinct shapes
    models = sorted(model_means['Model'].dropna().unique().tolist())
    model_markers = ['^', 's', 'D', 'P', 'X', '*', 'v', '<', '>', 'H']
    if len(models) > len(model_markers):
        raise ValueError(f"Not enough marker shapes for {len(models)} models; add more to model_markers.")

    model_to_marker = {m: model_markers[i] for i, m in enumerate(models)}

    # Color by player
    player_color = {'P-Red': 'red', 'P-Blue': 'blue'}

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(right=0.88)  # make room for legend on the right

    # Deterministic x positions
    xpos = {ct: i for i, ct in enumerate(order)}

    # Fixed offsets for models within each contract
    span = 0.12
    offsets = (
        [0.0] if len(models) == 1
        else list(np.linspace(-span, span, num=len(models)))
    )
    model_to_offset = {m: offsets[i] for i, m in enumerate(models)}

    # --- Per-model points ---
    for player in player_order:
        d_player = model_means[model_means['Player'] == player].copy()

        for m in models:
            d = d_player[d_player['Model'] == m].copy()
            if d.empty:
                continue

            xs = d['Contract Type'].map(xpos).to_numpy() + model_to_offset[m]
            ys = d['Reward'].to_numpy()

            ax.scatter(
                xs, ys,
                s=80,
                marker=model_to_marker[m],
                c=player_color[player],
                alpha=0.75,
                edgecolors='k',
                linewidths=0.4,
                zorder=2,
            )

    # --- Means ---
    for player in player_order:
        d = avg_stats[avg_stats['Player'] == player].copy()
        xs = d['Contract Type'].map(xpos).to_numpy()
        ys = d['mean_score'].to_numpy()
        yerr = np.nan_to_num(d['ci95'].to_numpy(), nan=0.0)

        ax.scatter(
            xs, ys,
            s=160,
            marker='o',
            c=player_color[player],
            alpha=1.0,
            edgecolors='k',
            linewidths=1.2,
            zorder=6,
        )

        ax.errorbar(
            xs, ys,
            yerr=yerr,
            fmt='none',
            ecolor=player_color[player],
            elinewidth=1.0,
            capsize=4,
            capthick=2.0,
            alpha=0.95,
            zorder=10,
        )

    # Baseline lines
    ax.axhline(y=baseline_p0, color='red', linestyle='--', linewidth=1.5)
    ax.axhline(y=baseline_p1, color='blue', linestyle='--', linewidth=1.5)

    # X axis ticks
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, fontsize=16)
    ax.set_ylabel('Reward', fontsize=16)
    ax.set_yticklabels(ax.get_yticks().astype(int), fontsize=16)

    # --- Right-side legend ---
    legend_font = 16

    # Player handles
    player_handles = [
        Line2D([0], [0], marker='o', linestyle='None', color=player_color['P-Red'],
               markerfacecolor=player_color['P-Red'], markeredgecolor='k',
               markeredgewidth=1.2, markersize=11, label='Mean (P-Red)'),
        Line2D([0], [0], marker='o', linestyle='None', color=player_color['P-Blue'],
               markerfacecolor=player_color['P-Blue'], markeredgecolor='k',
               markeredgewidth=1.2, markersize=11, label='Mean (P-Blue)'),
        Line2D([0], [0], color='red', linestyle='--', linewidth=1.5, label='Baseline P-Red'),
        Line2D([0], [0], color='blue', linestyle='--', linewidth=1.5, label='Baseline P-Blue'),
    ]

    # Model handles
    model_handles = [
        Line2D([0], [0], marker=model_to_marker[m], linestyle='None',
               markerfacecolor='0.6', markeredgecolor='k', markersize=10, label=m)
        for m in models
    ]

    # Player legend (top-right)
    leg_player = ax.legend(
        handles=player_handles,
        loc='upper left',
        bbox_to_anchor=(1., 1.0),
        fontsize=legend_font,
        frameon=True,
        title='Player',
        title_fontproperties={'weight': 'bold', 'size': legend_font},
        handletextpad=0.4,
        borderpad=0.6,
    )
    ax.add_artist(leg_player)

    # Model legend (below player legend)
    ax.legend(
        handles=model_handles,
        loc='upper left',
        bbox_to_anchor=(1.005, 0.55),
        fontsize=legend_font,
        frameon=True,
        title='Model',
        title_fontproperties={'weight': 'bold', 'size': legend_font},
        handletextpad=0.4,
        borderpad=0.6,
    )

    p4p_bool = df['Pay4Partner'].iloc[0] 
    p4p_str = 'p4p' if p4p_bool else 'regular_trading'
    name = f'{p4p_str}_player_scores_by_contract_for_{bucket}_with_baselines'
    output_path = f"{OUTPUT_FOLDER}/{name}.pdf"
    plt.savefig(output_path, format="pdf", bbox_inches="tight")
    print(f"Saved figure to {output_path}")

if __name__ == "__main__":
    df = format_data(FULL_DF, p4p=True)
    
    ##################### FIG 8 ####################
    graph_per_player_points(df)