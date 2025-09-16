
# %%


import pandas as pd
from itertools import islice


# Path to the JSONL file
jsonl_file = "board_finder/random_boards_and_properties_6_6.jsonl"
with open(jsonl_file, 'r') as f:
    df = pd.read_json(
        "".join(islice(f, 100)),  # take first 1000 lines
        lines=True
    )

# Expand the 'conditions' column into separate columns
conditions_df = pd.json_normalize(df['conditions'])

# Combine the original DataFrame with the expanded conditions DataFrame
df = pd.concat([df.drop(columns=['conditions']), conditions_df], axis=1)

# Display the formatted DataFrame
print(df.head())
# %%
df.columns
# %%
print(df.shape)
# %%
## doesn't doesn't
print(f"doesn't doesn't:{df[(df['B_10_path'] == True) & (df['R_10_path'] == True)].shape}")

# needs needs
print(f"needs needs: {df[
    (df['B_10_path'] == False) & (df['B_12_path'] == False) & (df['B_14_path'] == False) &
    (df['R_10_path'] == False) & (df['R_12_path'] == False) & (df['R_14_path'] == False)
].shape}")

# needs benefits
print(f" needs benefits: {df[
    (df['B_10_path'] == False) & (df['B_12_path'] == False) & (df['B_14_path'] == False) &
    (df['R_10_path'] == False) & ((df['R_12_path'] == True) | (df['R_14_path'] == True))
].shape}")

# needs doesn't
print(f" needs doesn't: {df[
    (df['B_10_path'] == False) & (df['B_12_path'] == False) & (df['B_14_path'] == False) &
    (df['R_10_path'] == True)
].shape}")

# benefits benefits
print(f"benefits benefits: {df[
    (df['B_10_path'] == False) & ((df['B_12_path'] == True) | (df['B_14_path'] == True)) &
    (df['R_10_path'] == False) & ((df['R_12_path'] == True) | (df['R_14_path'] == True))
].shape}")

# benefits doesn't
print(f"benefits doesn't: {df[
    (df['B_10_path'] == False) & ((df['B_12_path'] == True) | (df['B_14_path'] == True)) &
    (df['R_10_path'] == True)
].shape}")

# doesn't doesn't
print(f"doesn't doesn't: {df[
    (df['B_10_path'] == True) &
    (df['R_10_path'] == True)
].shape}")
# %%
# doesn't doesn't:(8055, 13)
# needs needs: (3509566, 13)
#  needs benefits: (5452, 13)
#  needs doesn't: (161890, 13)
# benefits benefits: (1, 13)
# benefits doesn't: (116, 13)
# doesn't doesn't: (8055, 13)
# %%

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'R', 'B', 'R', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'B', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'B', 'R'],
#  ['R', 'B', 'R', 'R', 'B', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'R', 'B', 'R', 'B', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]
# %%
# needs benefits
df[
    (df['R_10_path'] == False) & (df['R_12_path'] == False) & (df['R_14_path'] == False) &
    (df['B_10_path'] == False) & ((df['B_12_path'] == True) | (df['B_14_path'] == True))
].iloc[:3]['grid'].to_clipboard()
# %%

# needs doesn't
df[
    (df['R_10_path'] == False) & (df['R_12_path'] == False) & (df['R_14_path'] == False) &
    (df['B_10_path'] == True)
].iloc[:3]['grid'].to_clipboard()
# %%
