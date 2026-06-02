"""Generate cross-model individual scores table from log data."""
import json, glob
from collections import defaultdict
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 11,
    "mathtext.fontset": "cm",
})

BASE = 'public_logs/reduced_config_runs'

def compute_scores(model_pair, role):
    """Compute average score for a model in a pairing on MD boards.
    role: 'red' (P-Red score), 'blue' (P-Blue score), 'self' (avg both)
    """
    files = glob.glob(f'{BASE}/{model_pair}/Mutual_Dependency/**/event_log_*.json', recursive=True)
    files = [f for f in files if 'p4ptrue' in f]
    
    by_ct = defaultdict(list)
    for f in files:
        with open(f) as fh: d = json.load(fh)
        fs = d.get('game', {}).get('final_state')
        if not fs: continue
        scores = fs.get('scores', {})
        red = scores.get('P-Red', scores.get('Player 0', 0))
        blue = scores.get('P-Blue', scores.get('Player 1', 0))
        
        if 'contract_none' in f: ct = 'NC'
        elif 'contract_contract_for_finishing' in f: ct = 'PP'
        elif 'contract_strict' in f: ct = 'PT'
        elif 'contract_tile_with_judge' in f: ct = 'NLT'
        else: continue
        
        if role == 'self':
            by_ct[ct].append((red + blue) / 2)
        elif role == 'red':
            by_ct[ct].append(red)
        elif role == 'blue':
            by_ct[ct].append(blue)
    
    return {ct: f"{np.mean(vals):.1f}" for ct, vals in by_ct.items()}

# Define all rows
rows = [
    ('GPT-4.1', 'Self-play (avg both players)', 'FOUR_1-FOUR_1', 'self'),
    ('GPT-4.1', 'vs Haiku (GPT as P-Red, first mover)', 'FOUR_1-HAIKU_4_5', 'red'),
    ('GPT-4.1', 'vs Haiku (GPT as P-Blue)', 'HAIKU_4_5-FOUR_1', 'blue'),
    ('GPT-4.1', 'vs Qwen (GPT as P-Red, first mover)', 'FOUR_1-QWEN_3_30B', 'red'),
    ('GPT-4.1', 'vs Qwen (GPT as P-Blue)', 'QWEN_3_30B-FOUR_1', 'blue'),
    None,  # separator
    ('Haiku-4.5', 'Self-play (avg both players)', 'HAIKU_4_5-HAIKU_4_5', 'self'),
    ('Haiku-4.5', 'vs GPT (Haiku as P-Red, first mover)', 'HAIKU_4_5-FOUR_1', 'red'),
    ('Haiku-4.5', 'vs GPT (Haiku as P-Blue)', 'FOUR_1-HAIKU_4_5', 'blue'),
    None,  # separator
    ('Qwen-3-30B', 'Self-play (avg both players)', 'QWEN_3_30B-QWEN_3_30B', 'self'),
    ('Qwen-3-30B', 'vs GPT (Qwen as P-Red, first mover)', 'QWEN_3_30B-FOUR_1', 'red'),
    ('Qwen-3-30B', 'vs GPT (Qwen as P-Blue)', 'FOUR_1-QWEN_3_30B', 'blue'),
]

# Build table data
headers = ['Model', 'Pairing', 'NC', 'PP', 'NLT', 'PT']
table_data = []
for row in rows:
    if row is None:
        table_data.append(['', '', '', '', '', ''])
        continue
    model, pairing, pair_dir, role = row
    scores = compute_scores(pair_dir, role)
    table_data.append([
        model, pairing,
        scores.get('NC', '-'), scores.get('PP', '-'),
        scores.get('NLT', '-'), scores.get('PT', '-'),
    ])

# Print for verification
print("Verification:")
for row in table_data:
    if row[0]: print(f"  {row[0]:12s} {row[1]:45s} {row[2]:>6s} {row[3]:>6s} {row[4]:>6s} {row[5]:>6s}")

# Generate figure
fig, ax = plt.subplots(figsize=(16, 5.5))
ax.axis('off')

table = ax.table(cellText=table_data, colLabels=headers, loc='center', cellLoc='center',
                 colWidths=[0.12, 0.38, 0.1, 0.1, 0.1, 0.1])
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.0, 1.5)

for (row, col), cell in table.get_celld().items():
    cell.set_edgecolor('#CCCCCC')
    cell.set_linewidth(0.5)
    if row == 0:
        cell.set_facecolor('white')
        cell.set_text_props(fontweight='bold')
        cell.set_edgecolor('black')
        cell.set_linewidth(1.0)
    elif row > len(table_data): continue
    elif table_data[row-1][0] == '':
        cell.set_facecolor('white')
        cell.set_edgecolor('white')
    else:
        cell.set_facecolor('white')
    if col == 0 and row > 0 and row <= len(table_data):
        cell.set_text_props(fontweight='bold')
    if col == 1:
        cell.set_text_props(ha='left')
        cell.PAD = 0.02

fig.text(0.5, 0.02,
         'Table X: Individual model scores in cross-model and self-play settings on Mutually Dependent\n'
         'boards (Pay-for-Partner). We report the average score per player. NC = No Contract,\n'
         'PP = Prog-Points, NLT = NL-Trading, PT = Prog-Trading. P-Red is the first mover.',
         ha='center', fontsize=10, style='normal', family='serif')

fig.subplots_adjust(bottom=0.18, top=0.95)
output = 'analysis/figures/table_individual_scores.pdf'
fig.savefig(output, bbox_inches='tight')
print(f"\nSaved to {output}")
