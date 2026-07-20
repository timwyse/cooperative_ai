import pandas as pd

import ast
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import bootstrap
from matplotlib.lines import Line2D

pd.set_option("display.max_rows", 200)
pd.set_option("display.max_columns", None)


DEFAULT_FONT_SIZE = 16
mpl.rcParams.update({
    "font.size": DEFAULT_FONT_SIZE,         
    "axes.titlesize": DEFAULT_FONT_SIZE,
    "axes.labelsize": DEFAULT_FONT_SIZE,
    "legend.fontsize": DEFAULT_FONT_SIZE,
    "xtick.labelsize": DEFAULT_FONT_SIZE,
    "ytick.labelsize": DEFAULT_FONT_SIZE,
    "font.family":'monospace'
})


OUTPUT_FOLDER = "analysis/figures"
FULL_DF = pd.read_csv("results/all_runs_latest.csv")

MODEL_ORDER = ["GPT-4.1", "Haiku-4.5", "LLaMA Maverick", "LLaMA Scout", "Qwen-3-235B", "Qwen-3-30B"]
BUCKET_ORDER = ["Independent", "Mutually Dependent", "Asymmetric"]
CONTRACT_ORDER = ['No Contract', 'Prog-Points',   'NL-Trading', 'Prog-Trading']

def format_data(in_df, p4p=True):
    df = in_df.copy()
    df = df[df['Pay4Partner'] == p4p] 

    config_map = {
        "ctx1_fog00_p4pfalse_contract_contract_for_finishing_selfish11": "Finishing Contract",
        "ctx1_fog00_p4pfalse_contract_none_selfish11": "No Contract",
        "ctx1_fog00_p4pfalse_contract_strict_selfish11": "Strict Contract",
        "ctx1_fog00_p4pfalse_contract_tile_with_judge_implementation_selfish11": "Judge Contract",
        "ctx1_fog00_p4ptrue_contract_contract_for_finishing_selfish11": "P4P Finishing Contract",
        "ctx1_fog00_p4ptrue_contract_none_selfish11": "P4P No Contract",
        "ctx1_fog00_p4ptrue_contract_strict_selfish11": "P4P Strict Contract",
        "ctx1_fog00_p4ptrue_contract_tile_with_judge_implementation_selfish11": "P4P Judge Contract"
    }
    df['Config Label'] = df['Config ID'].map(config_map)
    df['Contract Type'] = df['Contract Type'].fillna('No Contract')
    df["Contract Type"] = df["Contract Type"].replace({
        "tile_with_judge_implementation": "NL-Trading",
        "strict": "Prog-Trading",
        "contract_for_finishing": "Prog-Points"
        })
    
    models = df["Model Pair"].str.partition("-")
    same_model = models[0] == models[2]
    # only analyze self-play games; cross-play pairs (e.g. FOUR_1-HAIKU_4_5) are handled separately
    df = df[same_model]
    models = models[same_model]
    df["Model"] = models[0]
    model_map = {
        "FOUR_1": "GPT-4.1",
        "HAIKU_4_5": "Haiku-4.5",
        "LLAMA_MAVERICK": "LLaMA Maverick",
        "LLAMA_SCOUT": "LLaMA Scout",
        "QWEN_3_235B": "Qwen-3-235B",
        "QWEN_3_30B": "Qwen-3-30B"
        }
    df["Model"] = df["Model"].map(model_map).fillna(df["Model"])
    df["Bucket"] = df["Bucket"].replace({
        "Independent (Both have optimal paths)": "Independent",
        "Mutual Dependency": "Mutually Dependent",
        "Needy Player (Blue)": "Asymmetric"
    })
    df['Board Type'] = df['Bucket']  
    
    # check if 0 or 1 have final leverage tile in the gir
    def _has_final_leverage_tile(grid_str: str, target: str) -> bool:
        g = ast.literal_eval(grid_str)  # safer than eval
        return (g[2][3] == target) and (g[3][2] == target)
    df["P-Red Has Final Leverage Tile"] = df["Grid"].apply(lambda s: _has_final_leverage_tile(s, "R"))
    df["P-Blue Has Final Leverage Tile"] = df["Grid"].apply(lambda s: _has_final_leverage_tile(s, "B"))
    df["Either Player Has Final Leverage Tile"] = df["P-Red Has Final Leverage Tile"] | df["P-Blue Has Final Leverage Tile"]

    # core metrics: both finished and accuracy
    df['Both Finished'] = (df['Reached Goal P-Red'] > 0) & (df['Reached Goal P-Blue'] > 0)
    df['Normalized Joint Reward'] = df['Joint Reward'] / df['Max Possible Reward']
    # df['Reward P-Red'] = df['Reward P-Red']
    # df['Reward P-Blue'] = df['Reward P-Blue']

    
    # beating baselines is core metric for NPB analysis
    # For independent it is not possbile for both to beat baseline
    # For MD , it is equivalent to both finishing
    df['R_beats_baseline'] = df['Reward P-Red'] > df['Non-Cooperative Baseline P-Red']
    df['B_beats_baseline'] = df['Reward P-Blue'] > df['Non-Cooperative Baseline P-Blue']
    df['Both Beat Baseline'] = df['R_beats_baseline'] & df['B_beats_baseline']
    df['All Beat Baseline'] = df['Both Beat Baseline']
    df['Both Beat Zero Cooperation Baseline'] = df['Both Beat Baseline']
    
    ## equality measures
    ## use this to look at first mover advantage for contracts, as well as if P0 can leverage its better situation in NPB
    # points_proportion_P-Red another core metric (i prefer it to gini b/c easier to interpret)
    df["Proportion of Total Points for P-Red"] = df['Reward P-Red'] / (df['Reward P-Red'] + df['Reward P-Blue'])
    df['trade_volume_proportion_P-Red'] = df['amount_received_by_P-Red_from_trades'] / (df['amount_received_by_P-Red_from_trades'] + df['amount_received_by_P-Blue_from_trades'])
    # note that P-Blue keeping a p4p promise is equivalent to P-Red receiving a p4p payment
    df['p4p_volume_proportion_P-Red'] = df['Total P4P Promises Kept P-Blue'] / (df['Total P4P Promises Kept P-Blue'] + df['Total P4P Promises Kept P-Red'])
    df['strict_contract_tile_proportion_P-Red'] = df['num_tiles_promised_to_receive_from_contract_P-Red'] / (df['num_tiles_promised_to_receive_from_contract_P-Red'] + df['num_tiles_promised_to_receive_from_contract_P-Blue'])
    df['net_tiles_promised_to_receive_from_contract_P-Red'] = df['num_tiles_promised_to_receive_from_contract_P-Red'] - df['num_tiles_promised_to_receive_from_contract_P-Blue']
    df['net_tiles_promised_to_receive_from_contract_P-Blue'] = df['num_tiles_promised_to_receive_from_contract_P-Blue'] - df['num_tiles_promised_to_receive_from_contract_P-Red']
    df['strict_tile_gini'] = (df['num_tiles_promised_to_receive_from_contract_P-Red'] - df['num_tiles_promised_to_receive_from_contract_P-Blue']).abs() / ((2)*(df['num_tiles_promised_to_receive_from_contract_P-Red'] + df['num_tiles_promised_to_receive_from_contract_P-Blue']))
    df['strict_tile_even_split'] = (df['num_tiles_promised_to_receive_from_contract_P-Red'] == df['num_tiles_promised_to_receive_from_contract_P-Blue'])
    df['strict_tile_winner_take_all'] = ((df['num_tiles_promised_to_receive_from_contract_P-Red'] == 0) | (df['num_tiles_promised_to_receive_from_contract_P-Blue'] == 0)) & (df['num_tiles_promised_to_receive_from_contract_P-Red'] + df['num_tiles_promised_to_receive_from_contract_P-Blue'] > 0)

    df['contract_for_finishing_points_proportion_P-Red'] = df['points_for_completion_promised_to_P-Red'] / (df['points_for_completion_promised_to_P-Red'] + df['points_for_completion_promised_to_P-Blue'])
    df['contract_for_finishing_points_gini'] = (df['points_for_completion_promised_to_P-Red'] - df['points_for_completion_promised_to_P-Blue']).abs() / (2*(df['points_for_completion_promised_to_P-Red'] + df['points_for_completion_promised_to_P-Blue']))
    df['contract_for_finishing_points_even_split'] = (df['points_for_completion_promised_to_P-Red'] == df['points_for_completion_promised_to_P-Blue'])
    df['contract_for_finishing_points_winner_take_all'] = ((df['points_for_completion_promised_to_P-Red'] == 0) | (df['points_for_completion_promised_to_P-Blue'] == 0)) & (df['points_for_completion_promised_to_P-Red'] + df['points_for_completion_promised_to_P-Blue'] > 0)
    df['net_points_for_completion_promised_to_P-Red'] = df['points_for_completion_promised_to_P-Red'] - df['points_for_completion_promised_to_P-Blue']
    df['net_points_for_completion_promised_to_P-Blue'] = df['points_for_completion_promised_to_P-Blue'] - df['points_for_completion_promised_to_P-Red']
    
    contract_conditions = [(df['Contract Type'] == 'Prog-Points'), (df['Contract Type'] == 'Prog-Trading'), (df['Contract Type'] == 'NL-Trading')]
    contract_gini_choices = [df['contract_for_finishing_points_gini'], df['strict_tile_gini'], df['strict_tile_gini']]
    df['Contract Gini'] = np.select(contract_conditions, contract_gini_choices, default=np.nan)

    contract_even_split_choices = [df['contract_for_finishing_points_even_split'], df['strict_tile_even_split'], df['strict_tile_even_split']]
    df['Contract Even Split'] = np.select(contract_conditions, contract_even_split_choices, default=np.nan)

    contract_winner_take_all_choices = [df['contract_for_finishing_points_winner_take_all'], df['strict_tile_winner_take_all'], df['strict_tile_winner_take_all']]
    df['Contract Winner Take All'] = np.select(contract_conditions, contract_winner_take_all_choices, default=np.nan)

    contract_net_p_red_choices = [df['net_points_for_completion_promised_to_P-Red'], df['net_tiles_promised_to_receive_from_contract_P-Red'], df['net_tiles_promised_to_receive_from_contract_P-Red']]
    df['Contract Net P-Red'] = np.select(contract_conditions, contract_net_p_red_choices, default=np.nan)
 
    ## cooperation metrics
    df['total_trade_volume'] = df['amount_received_by_P-Red_from_trades'] + df['amount_received_by_P-Blue_from_trades']
    df['Trade Volume'] = df['total_trade_volume']
    df['trade_acceptance_rate_P-Red'] = df['Total Trades Accepted P-Red'] / df['Total Trades Proposed P-Blue']
    df['trade_acceptance_rate_P-Blue'] = df['Total Trades Accepted P-Blue'] / df['Total Trades Proposed P-Red']
    df['total_trade_acceptance_rate'] = (df['Total Trades Accepted P-Red'] + df['Total Trades Accepted P-Blue']) / (df['Total Trades Proposed P-Red'] + df['Total Trades Proposed P-Blue'])
    df['moves_made_under_strict_contract_total'] = df['moves_made_under_strict_contract_P-Red'] + df['moves_made_under_strict_contract_P-Blue']
    df['Moves Made Under Strict Contract'] = df['moves_made_under_strict_contract_total']
    df['Total Trades Proposed'] = df['Total Trades Proposed P-Red'] + df['Total Trades Proposed P-Blue']

    df['parity_trade_acceptance_rate'] = (df['parity_trades_accepted_P-Red'] + df['parity_trades_accepted_P-Blue']) / (df['parity_trades_offered_P-Red'] + df['parity_trades_offered_P-Blue'])
    
    # if 0 accepts a concessionary trade, that means 1 proposed a extractive trade etc
    df['extractive_trades_acceptance_rate'] = (df['concessionary_trades_accepted_P-Red'] + df['concessionary_trades_accepted_P-Blue']) / (df['extractive_trades_offered_P-Red'] + df['extractive_trades_offered_P-Blue'])
    df['concessionary_trades_acceptance_rate'] = (df['extractive_trades_accepted_P-Red'] + df['extractive_trades_accepted_P-Blue']) / (df['concessionary_trades_offered_P-Red'] + df['concessionary_trades_offered_P-Blue'])

    # make bad trade flag
    any_parity = (df["parity_trades_offered_P-Red"] > 0) | (df["parity_trades_offered_P-Blue"] > 0)
    any_conc_offered = (df["concessionary_trades_offered_P-Red"] > 0) | (df["concessionary_trades_offered_P-Blue"] > 0)
    any_extractive_accepted = (df["extractive_trades_accepted_P-Red"] > 0) | (df["extractive_trades_accepted_P-Blue"] > 0)


    # parity / concessionary trade by *red* (P-Red)
    red_parity = df["parity_trades_offered_P-Red"] > 0
    red_conc   = df["concessionary_trades_offered_P-Red"] > 0
    red_parity_accepted = df["parity_trades_accepted_P-Red"] > 0
    red_conc_accepted   = df["concessionary_trades_accepted_P-Red"] > 0

    cond_independent = df["Bucket"] == "Independent"
    cond_md = df["Bucket"] == "Mutually Dependent"
    cond_asymmetric  = df["Bucket"] == "Asymmetric"
    

    df["Bad Trade"] = False
    df.loc[cond_independent & (any_parity | any_conc_offered | any_extractive_accepted), "Bad Trade"] = True
    # df.loc[cond_md & (any_conc_offered | any_extractive_accepted), "Bad Trade"] = True
    df.loc[cond_asymmetric  & (red_parity | red_conc | red_parity_accepted | red_conc_accepted), "Bad Trade"] = True


    # P4P promise honour rates
    df['P4P Promise Honour Rate P-Red'] = df['Total P4P Promises Kept P-Red'] / (df['Total P4P Promises Kept P-Red'] + df['Total P4P Promises Broken P-Red'])
    df['P4P Promise Honour Rate P-Blue'] = df['Total P4P Promises Kept P-Blue'] / (df['Total P4P Promises Kept P-Blue'] + df['Total P4P Promises Broken P-Blue'])
    df['Total P4P Promise Honour Rate'] = (df['Total P4P Promises Kept'] ) / (df['Total P4P Promises Kept'] + df['Total P4P Promises Broken'])
    df['Defection Rate'] =  (df['Total P4P Promises Broken'] ) / (df['Total P4P Promises Kept'] + df['Total P4P Promises Broken'])
    df['Defection Volume'] = df['Total P4P Promises Broken']

    for model in df['Model'].unique():
        print(f"{model} has {len(df[df['Model'] == model])} rows.")

    print(f"Formatted data with {len(df['Model Pair'].unique())} unique model pairs,  {len(df)} total rows")
    return df