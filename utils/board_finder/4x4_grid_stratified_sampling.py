import pandas as pd
import json
import yaml
import pandas as pd
import numpy as np


# Path to 4x4 generated grids generated from find_paths.py
file_path = "boards_properties_4_by_4.jsonl"

# Read JSONL into an initial DataFrame, coercing errors to NaN
df = pd.read_json(file_path, lines=True)

# Convert the DataFrame to a list of dictionaries (records)
# This is the ideal format for json_normalize to work on the whole dataset
records = df.to_dict('records')

# Normalize the entire list of records. This flattens 'conditions' and 'analysis'
# while keeping the top-level 'grid' column.
df_expanded = pd.json_normalize(records)

# Create a list of all column names that start with 'analysis.'
analysis_cols = [col for col in df_expanded.columns if col.startswith('analysis.')]

# Create a final list of columns to keep: 'grid' + all the analysis columns
cols_to_keep = ['grid'] + analysis_cols

# Create the new DataFrame with only the columns you want
df_to_sample = df_expanded[cols_to_keep]

# The number of samples you want to draw from each specific sub-type.
N_PER_SUB_STRATUM = 20

# Work on a copy of DataFrame.
df = df_to_sample.copy()

# Create the Detailed Sub-Strata Column
# We define conditions and choices based on column values
# (e.g., 'analysis.bucket', 'analysis.metrics.b_min_trades_efficient_path').

conditions = [
    # Mutual Dependency sub-types (e.g., MD (1,2))
    (df['analysis.bucket'] == 'Mutual Dependency'),

    # Needy Player sub-types (e.g., NP-Blue (Need=1))
    (df['analysis.bucket'] == 'Needy Player (Blue)'),
    (df['analysis.bucket'] == 'Needy Player (Red)'),
]

choices = [
    # Mutual Dependency choices
    'MD (' + df['analysis.metrics.b_min_trades_efficient_path'].astype(str) + ',' + df['analysis.metrics.r_min_trades_efficient_path'].astype(str) + ')',

    # Needy Player choices
    'NP-Blue (Need=' + df['analysis.metrics.b_min_trades_efficient_path'].astype(str) + ')',
    'NP-Red (Need=' + df['analysis.metrics.r_min_trades_efficient_path'].astype(str) + ')',
]

# Create the new 'sub_stratum' column.
# Any bucket NOT in our conditions (like 'Independent') will
# keep its original name, creating a single stratum for it.
df['sub_stratum'] = np.select(conditions, choices, default=df['analysis.bucket'])

# Perform the Stratified Sample
# We group by our new sub_stratum column and take N samples from each group.
# The resulting DataFrame will contain all the original columns, including 'grid'.

stratified_sample_df = df.groupby('sub_stratum', group_keys=False).apply(
    lambda x: x.sample(n=min(len(x), N_PER_SUB_STRATUM))
)

# Create a list of columns to keep
columns_to_keep = [
    'grid',
    'analysis.bucket',
    'analysis.metrics.b_min_trades_efficient_path',
    'analysis.metrics.b_max_trades_efficient_path',
    'analysis.metrics.r_min_trades_efficient_path',
    'analysis.metrics.r_max_trades_efficient_path',
    'analysis.metrics.trade_asymmetry',
    'sub_stratum'
]

# Create the new DataFrame containing only those columns
final_sample_df = stratified_sample_df[columns_to_keep]

# Create a list of the specific buckets of interest
buckets_to_keep = [
    'Mutual Dependency',
    'Needy Player (Red)',
    'Needy Player (Blue)',
    'Independent (Both have optimal paths)'
]

# Filter the DataFrame
# This keeps only the rows where the 'analysis.bucket' value
# is present in your 'buckets_to_keep' list.
filtered_df = final_sample_df[final_sample_df['analysis.bucket'].isin(buckets_to_keep)]

# Clean column names
# Remove the 'analysis.metrics.' prefix first
filtered_df.columns = filtered_df.columns.str.replace('analysis.metrics.', '', regex=False)

# Then remove the remaining 'analysis.' prefix
filtered_df.columns = filtered_df.columns.str.replace('analysis.', '', regex=False)

# Reset index and create a new column 'id' then assign index values to it.
filtered_df = filtered_df.reset_index(drop=True)
filtered_df['id'] = filtered_df.index

# Reorder column names so id shows up first
column_order = ['id'] + [col for col in filtered_df.columns if col != 'id']
filtered_df = filtered_df[column_order]

# 1. Convert the DataFrame to a list of dictionaries
# Each dictionary in the list represents one board and its characteristics.
boards_for_experiment = filtered_df.to_dict('records')

# 2. Save the list of boards to a YAML file
yaml_file_path = '4x4_experiment_grids.yaml'
with open(yaml_file_path, 'w') as f:
    yaml.dump(boards_for_experiment, f, sort_keys=False, default_flow_style=None, indent=2)

print(f"Successfully saved {len(boards_for_experiment)} boards to {yaml_file_path}")

