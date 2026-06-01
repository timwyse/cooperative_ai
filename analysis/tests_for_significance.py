
from scipy import stats
from format_results import format_data, FULL_DF

def test_for_significant_difference(hyp_smaller_set, hyp_bigger_set):
# Split into two groups
    
    # One-sided Mann-Whitney U test:
    # H0: No Contract >= Prog-Trading
    # H1: No Contract < Prog-Trading (alternative='less')
    u_stat, p_val = stats.mannwhitneyu(hyp_smaller_set, hyp_bigger_set, alternative='less')

    # Also run a t-test for reference
    t_stat, p_ttest = stats.ttest_ind( hyp_smaller_set, hyp_bigger_set, alternative='less')

    print("=" * 55)
    
    # print(f"  No Contract  — mean={no_contract.mean():.3f}, n={len(no_contract)}")
    # print(f"  Prog-Trading — mean={prog_trading.mean():.3f}, n={len(prog_trading)}")
    # print()
    print(f"  Mann-Whitney U = {u_stat:.1f},  p = {p_val:.4g}")
    print(f"  Welch t-test   t = {t_stat:.3f},  p = {p_ttest:.4g}")
    print()
    if p_val < 0.05:
        print("  ✓ Significant at α=0.05 (Mann-Whitney)")
    else:
        print("  ✗ Not significant at α=0.05 (Mann-Whitney)")
    print("=" * 55)

if __name__ == "__main__":
    df = format_data(FULL_DF, p4p=True)
    
    # Thus agents can rely less on Pay-for-Partner arrangements, and there are 38%
    # less Pay-for-Partner arrangements in Prog-Points than in No-Contract settings (t-test; p <
    # 0.001)
    no_contract = df[df['Contract Type'] == 'No Contract']['Total P4P Arrangements Accepted']
    prog_trading = df[df['Contract Type'] == 'Prog-Trading']['Total P4P Arrangements Accepted']

    test_for_significant_difference(prog_trading, no_contract)

    
    
    # Under
    # Prog-Trading P-Blue achieves substantially higher rewards with average reward 68% higher
    # than in the No-Contract setting (t-test; p < 0.001)
    no_contract = df[(df['Contract Type'] == 'No Contract') & (df['Board Type'] == 'Asymmetric')]['Reward P-Blue'].dropna()
    prog_trading = df[(df['Contract Type'] == 'Prog-Trading') & (df['Board Type'] == 'Asymmetric')]['Reward P-Blue'].dropna()
    test_for_significant_difference(no_contract, prog_trading)


    # Overall, agents
    # are highly likely to reach agreements, with most models accepting contracts 86% of the
    # time on average. Haiku-4.5 is a notable exception, with a mean acceptance rate of 67%
    # (t-test; p < 0.001)
    haiku = df[(df['Contract Type'].isin(['Prog-Trading', 'Prog-Points'])) & (df['Model'] == 'Haiku-4.5')]['contract_accepted'].dropna()
    other_models = df[(df['Contract Type'].isin(['Prog-Trading', 'Prog-Points'])) & (df['Model'] != 'Haiku-4.5')]['contract_accepted'].dropna()
    test_for_significant_difference(haiku, other_models)


    # These settings exhibit
    # the highest Gini values, and in 39% of boards only one player gets any points from the
    # other for finishing (Winner Takes All). This effect is particularly pronounced for the Qwen
    # models, where this happens in 74% of cases on Asymmetric boards (t-test; p < 0.001).

    qwen = df[(df['Contract Type'].isin(['Prog-Points'])) & (df['Board Type'] == 'Asymmetric') & (df['Model'].isin(['Qwen-3-235B', 'Qwen-3-30B']))]['Contract Winner Take All'].dropna()

    other_models = df[(df['Contract Type'].isin(['Prog-Points'])) & (df['Board Type'] == 'Asymmetric') & (~df['Model'].isin(['Qwen-3-235B', 'Qwen-3-30B']))]['Contract Winner Take All'].dropna()

    test_for_significant_difference(other_models, qwen)
