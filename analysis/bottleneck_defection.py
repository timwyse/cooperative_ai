
import pandas as pd
import ast
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import bootstrap
from matplotlib.lines import Line2D

from format_results import format_data, MODEL_ORDER, BUCKET_ORDER, CONTRACT_ORDER, FULL_DF, DEFAULT_FONT_SIZE, OUTPUT_FOLDER


def bottleneck_defection_by_contract(df):
    leverage_df = df[df['Bucket'] == 'Mutually Dependent'].copy()

    # Build long-form: one row per player per game
    rows = []
    for _, r in leverage_df.iterrows():
        for player, other in [('P-Red', 'P-Blue'), ('P-Blue', 'P-Red')]:
            has_leverage = r[f'{player} Has Final Leverage Tile']
            honour_rate = r[f'P4P Promise Honour Rate {player}']
            if has_leverage:
                rows.append({
                    'Contract Type': r['Contract Type'],
                    'Defection Rate': 1 - honour_rate if not np.isnan(honour_rate) else np.nan,
                    'Player': player,
                    'Model': r.get('Model', ''),
                })

    long_df = pd.DataFrame(rows)
    long_df = long_df.dropna(subset=['Defection Rate'])

    # Summary by contract type
    summary = (
        long_df
        .groupby(['Contract Type'], observed=True)
        .agg(
            mean_defection=('Defection Rate', 'mean'),
            std_defection=('Defection Rate', 'std'),
            n=('Defection Rate', 'count'),
        )
        .reset_index()
    )

    print(summary.to_string(index=False))

    # Plot
    fig, ax = plt.subplots(figsize=(8, 5))

    contract_order_filtered = [c for c in CONTRACT_ORDER if c in summary['Contract Type'].unique()]
    xpos = {ct: i for i, ct in enumerate(contract_order_filtered)}
    bar_width = 0.5

    d = summary.copy()
    xs = d['Contract Type'].map(xpos).to_numpy()
    ys = d['mean_defection'].to_numpy()
    yerr = d['std_defection'].to_numpy() / np.sqrt(d['n'].to_numpy())
    ax.bar(xs, ys, width=bar_width, color='tab:cyan', alpha=0.7, edgecolor='k', linewidth=0.5)
    ax.errorbar(xs, ys, yerr=1.96 * yerr, fmt='none', ecolor='k', capsize=4, capthick=1.2)

    ax.set_xticks(range(len(contract_order_filtered)))
    ax.set_xticklabels(contract_order_filtered, fontsize=DEFAULT_FONT_SIZE)
    ax.set_ylabel('Defection Rate', fontsize=DEFAULT_FONT_SIZE)
    ax.set_ylim(0, 1.05)
    ax.grid(axis='y', alpha=0.15)

    output_path = f"{OUTPUT_FOLDER}/bottleneck_defection_rate_by_contract.pdf"
    plt.savefig(output_path, format="pdf", bbox_inches="tight")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    df = format_data(FULL_DF, p4p=True)
    
    ##################### FIG 11 ####################
    bottleneck_defection_by_contract(df)