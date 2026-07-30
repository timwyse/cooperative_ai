"""
Classify negotiation tactics from verbose game logs.

Usage:
    python analysis/classify_negotiation_tactics.py [--logs-dir LOGS_DIR] [--output-dir OUTPUT_DIR]

Defaults:
    --logs-dir: public_logs/reduced_config_runs
    --output-dir: analysis/
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_DISPLAY_NAMES = {
    "FOUR_1-FOUR_1": "GPT-4.1",
    "HAIKU_4_5-HAIKU_4_5": "Haiku-4.5",
    "LLAMA_MAVERICK-LLAMA_MAVERICK": "LLaMA Maverick",
    "LLAMA_SCOUT-LLAMA_SCOUT": "LLaMA Scout",
    "QWEN_3_235B-QWEN_3_235B": "Qwen-3-235B",
    "QWEN_3_30B-QWEN_3_30B": "Qwen-3-30B",
}

BUCKET_DISPLAY = {
    "Mutual_Dependency": "Mutual Dependency",
    "Needy_Player_Blue": "Asymmetric",
    "Independent_Both_have_optimal_paths": "Independent",
}

CONTRACT_DISPLAY = {
    "finishing": "Finishing",
    "strict": "Strict",
    "tile_judge": "Tile-Judge",
}

TACTIC_COLUMNS = [
    "tactic_anchoring",
    "tactic_take_it_or_leave_it",
    "tactic_no_deal_walkaway",
    "tactic_power_asymmetry",
    "tactic_mutual_verification",
    "tactic_path_analysis",
    "tactic_deception_suspected",
    "tactic_incremental_concessions",
]

TACTIC_DISPLAY = {
    "tactic_anchoring": "Anchoring",
    "tactic_take_it_or_leave_it": "Take-it-or-leave-it",
    "tactic_no_deal_walkaway": "No-deal Walk-away",
    "tactic_power_asymmetry": "Power Asymmetry",
    "tactic_mutual_verification": "Mutual Verification",
    "tactic_path_analysis": "Path Analysis",
    "tactic_deception_suspected": "Deception (suspected)",
    "tactic_incremental_concessions": "Incremental Concessions",
}

FOCUS_MODEL = "GPT-4.1"


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

def find_verbose_logs(logs_dirs):
    """Find all verbose_log JSON files across directories."""
    paths = []
    for d in logs_dirs:
        paths.extend(glob.glob(os.path.join(d, "**", "verbose_log_*.json"), recursive=True))
    return sorted(paths)


def parse_model_pair(path):
    """Extract model pair from log path."""
    parts = Path(path).parts
    for known in MODEL_DISPLAY_NAMES:
        if known in parts:
            return known
    return None


def parse_bucket(path):
    """Extract board bucket from log path."""
    parts = Path(path).parts
    for known in BUCKET_DISPLAY:
        if known in parts:
            return known
    return None


def parse_contract_type(path):
    """Extract contract type from log path."""
    path_str = str(path)
    if "contract_for_finishing" in path_str:
        return "finishing"
    elif "contract_strict" in path_str:
        return "strict"
    elif "contract_tile_with_judge" in path_str:
        return "tile_judge"
    elif "contract_none" in path_str:
        return "none"
    return "unknown"


def parse_grid_id(path):
    """Extract grid id from log path."""
    parts = Path(path).parts
    for p in parts:
        if p.startswith("grid_"):
            return p
    return None


def get_non_system_messages(conversation_history):
    """Filter out system messages."""
    return [m for m in conversation_history if m.get("role") != "system"]


def get_all_message_texts(cn, include_system=False):
    """Get all message texts from both conversation histories."""
    texts = []
    for key in ("conversation_history_0", "conversation_history_1"):
        for msg in cn.get(key, []):
            if include_system or msg.get("role") != "system":
                texts.append(msg.get("content", ""))
    return texts


def get_player_messages(cn, player_idx):
    """Get assistant messages from a player's conversation history."""
    key = f"conversation_history_{player_idx}"
    return [
        m.get("content", "")
        for m in cn.get(key, [])
        if m.get("role") == "assistant"
    ]


# ---------------------------------------------------------------------------
# Finishing contract point transfer extraction
# ---------------------------------------------------------------------------

def extract_finishing_transfers(judge_contract):
    """Extract (p0_gives, p1_gives) point transfers from a finishing contract."""
    if not judge_contract:
        return None, None
    p0_entry = judge_contract.get("player_0_reaches_goal", {})
    p1_entry = judge_contract.get("player_1_reaches_goal", {})
    try:
        p0_gives = int(p0_entry.get("amount", 0))
    except (ValueError, TypeError):
        p0_gives = 0
    try:
        p1_gives = int(p1_entry.get("amount", 0))
    except (ValueError, TypeError):
        p1_gives = 0
    return p0_gives, p1_gives


def classify_transfer_pattern(p0_gives, p1_gives):
    """Classify the finishing contract transfer pattern."""
    if p0_gives == 0 and p1_gives == 0:
        return "(0,0)"
    elif (p0_gives == 0 and p1_gives == 20) or (p0_gives == 20 and p1_gives == 0):
        return "(0,20)"
    elif p0_gives == 10 and p1_gives == 10:
        return "(10,10)"
    else:
        return "Other"


# ---------------------------------------------------------------------------
# Tactic classification heuristics
# ---------------------------------------------------------------------------

def extract_numbers(text):
    """Extract all numbers from a text string."""
    return [int(x) for x in re.findall(r"\b(\d+)\b", text)]


def detect_anchoring(cn, contract_type):
    """Detect anchoring: first proposal contains extreme asymmetry."""
    msgs_p0 = get_player_messages(cn, 0)
    msgs_p1 = get_player_messages(cn, 1)
    first_proposal = msgs_p0[0] if msgs_p0 else (msgs_p1[0] if msgs_p1 else "")
    if not first_proposal:
        return False

    text = first_proposal.lower()

    if contract_type == "finishing":
        numbers = extract_numbers(first_proposal)
        for n in numbers:
            if n >= 16 and n <= 20:
                if any(kw in text for kw in ["point", "give", "transfer", "pay", "receive"]):
                    return True
        if re.search(r"\b(0|zero)\b.*\b(20|twenty)\b|\b(20|twenty)\b.*\b(0|zero)\b", text):
            return True
    elif contract_type == "strict":
        tile_counts = re.findall(r"(\d+)\s*(?:tile|chip|resource)", text)
        if len(tile_counts) >= 2:
            vals = [int(x) for x in tile_counts]
            if max(vals) >= 3 * min(vals) and min(vals) > 0:
                return True
        give_nums = re.findall(r"(?:give|provide|offer)\s*(?:you\s+)?(\d+)", text)
        receive_nums = re.findall(r"(?:receive|get|want)\s*(\d+)", text)
        if give_nums and receive_nums:
            g = max(int(x) for x in give_nums)
            r = max(int(x) for x in receive_nums)
            if r > 0 and g / r >= 3:
                return True
    return False


def detect_take_it_or_leave_it(cn):
    """Detect take-it-or-leave-it: <= 3 non-system messages AND agreement."""
    if not cn.get("agreement_status", False):
        return False
    msgs = get_non_system_messages(cn.get("conversation_history_0", []))
    return len(msgs) <= 3


def detect_no_deal_walkaway(cn):
    """Detect no-deal walk-away: rejection or (0,0) with explicit refusal."""
    if not cn.get("agreement_status", False):
        return True

    for key in ("agreement_from_player_0", "agreement_from_player_1"):
        resp = cn.get(key, {})
        if isinstance(resp, dict):
            parsed = resp.get("parsed", {})
            if isinstance(parsed, dict):
                status = parsed.get("status", "").lower()
                if status in ("rejected", "disagreed"):
                    return True

    jc = cn.get("judge_contract", {})
    if "player_0_reaches_goal" in jc:
        p0_gives, p1_gives = extract_finishing_transfers(jc)
        if p0_gives == 0 and p1_gives == 0:
            all_text = " ".join(get_all_message_texts(cn)).lower()
            refusal_phrases = [
                "don't need", "do not need", "no cooperation",
                "no deal", "refuse", "won't cooperate",
                "don't want to cooperate", "not interested",
            ]
            if any(phrase in all_text for phrase in refusal_phrases):
                return True
    return False


def detect_power_asymmetry(cn):
    """Detect power asymmetry exploitation in messages."""
    all_text = " ".join(get_all_message_texts(cn)).lower()
    power_phrases = [
        "i can reach my goal without",
        "i don't need you",
        "i do not need you",
        "you cannot reach",
        "you can't reach",
        "you need me",
        "self-sufficient",
        "independently",
        "without any help",
        "without your help",
        "i don't need any",
        "i do not need any",
        "don't need cooperation",
        "without assistance",
        "reach my goal on my own",
    ]
    return any(phrase in all_text for phrase in power_phrases)


def detect_mutual_verification(cn):
    """Detect mutual verification: both players reference coordinates + verification language."""
    verification_words = ["verify", "confirm", "check", "correct", "recalculate", "double-check"]
    coord_pattern = r"\(\d+\s*,\s*\d+\)"

    player_has_verification = [False, False]
    for player_idx in range(2):
        msgs = get_player_messages(cn, player_idx)
        combined = " ".join(msgs).lower()
        has_coords = bool(re.search(coord_pattern, combined))
        has_verify = any(w in combined for w in verification_words)
        player_has_verification[player_idx] = has_coords and has_verify

    return all(player_has_verification)


def detect_path_analysis(cn):
    """Detect path analysis: arrow notation or coordinate-heavy cost breakdowns."""
    all_text = " ".join(get_all_message_texts(cn))

    arrow_pattern = r"\(\d+\s*,\s*\d+\)\s*->\s*\(\d+\s*,\s*\d+\)"
    if re.search(arrow_pattern, all_text):
        return True

    coords = re.findall(r"\(\d+\s*,\s*\d+\)", all_text)
    cost_words = ["cost", "chip", "spend", "require", "need", "use"]
    text_lower = all_text.lower()
    has_costs = any(w in text_lower for w in cost_words)
    if len(coords) >= 4 and has_costs:
        return True

    return False


def detect_deception_suspected(cn, game_data=None):
    """Detect suspected deception: inconsistent claims or reversal."""
    all_text = " ".join(get_all_message_texts(cn)).lower()

    reversal_phrases = [
        "actually, i changed my mind",
        "i'll take a different",
        "let me revise",
        "on second thought",
        "i lied",
        "that's not true",
        "i was bluffing",
    ]
    if any(phrase in all_text for phrase in reversal_phrases):
        return True

    chip_claims = re.findall(r"i have (\d+)\s*(red|blue|green|yellow)", all_text)
    if len(chip_claims) >= 2:
        colors_claimed = defaultdict(list)
        for count, color in chip_claims:
            colors_claimed[color].append(int(count))
        for color, counts in colors_claimed.items():
            if len(set(counts)) > 1:
                return True

    return False


def detect_incremental_concessions(cn):
    """Detect incremental concessions: >= 6 messages with decreasing proposal gaps."""
    msgs = get_non_system_messages(cn.get("conversation_history_0", []))
    if len(msgs) < 6:
        return False

    proposals = []
    for msg in msgs:
        content = msg.get("content", "")
        numbers = extract_numbers(content)
        relevant = [n for n in numbers if 0 <= n <= 20]
        if relevant:
            proposals.append(max(relevant))

    if len(proposals) >= 3:
        gaps = [abs(proposals[i+1] - proposals[i]) for i in range(len(proposals)-1)]
        decreasing_count = sum(1 for i in range(len(gaps)-1) if gaps[i+1] < gaps[i])
        if decreasing_count >= 2:
            return True

    return False


# ---------------------------------------------------------------------------
# Log counting and classification
# ---------------------------------------------------------------------------

def count_logs_by_group(log_paths):
    """Count log files per (model_display, bucket_display, contract_type) from paths alone.

    This is the ground truth 'n' -- it counts files on disk regardless of
    whether they parse successfully or contain a contract_negotiation entry.
    """
    counts = defaultdict(int)
    for path in log_paths:
        model_pair = parse_model_pair(path)
        bucket = parse_bucket(path)
        contract_type = parse_contract_type(path)
        model_display = MODEL_DISPLAY_NAMES.get(model_pair, model_pair or "Unknown")
        bucket_display = BUCKET_DISPLAY.get(bucket, bucket or "Unknown")
        counts[(model_display, bucket_display, contract_type)] += 1
    return dict(counts)


def classify_negotiation(log_path):
    """Classify negotiation tactics for all turns in a verbose log."""
    try:
        with open(log_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    model_pair = parse_model_pair(log_path)
    bucket = parse_bucket(log_path)
    contract_type = parse_contract_type(log_path)
    grid_id = parse_grid_id(log_path)

    if contract_type in ("none", "unknown"):
        return []

    game = data.get("game", {})
    turns = game.get("turns", {})

    results = []
    for turn_key, turn_data in turns.items():
        cn = turn_data.get("contract_negotiation")
        if not cn:
            continue

        agreement_status = cn.get("agreement_status", False)
        if isinstance(agreement_status, bool):
            agreement_str = "agreed" if agreement_status else "rejected"
        else:
            agreement_str = str(agreement_status)

        conv_msgs = get_non_system_messages(cn.get("conversation_history_0", []))
        conv_length = len(conv_msgs)

        row = {
            "model_pair": MODEL_DISPLAY_NAMES.get(model_pair, model_pair or "Unknown"),
            "bucket": BUCKET_DISPLAY.get(bucket, bucket or "Unknown"),
            "grid_id": grid_id or "Unknown",
            "contract_type": contract_type,
            "agreement_status": agreement_str,
            "conversation_length": conv_length,
            "tactic_anchoring": detect_anchoring(cn, contract_type),
            "tactic_take_it_or_leave_it": detect_take_it_or_leave_it(cn),
            "tactic_no_deal_walkaway": detect_no_deal_walkaway(cn),
            "tactic_power_asymmetry": detect_power_asymmetry(cn),
            "tactic_mutual_verification": detect_mutual_verification(cn),
            "tactic_path_analysis": detect_path_analysis(cn),
            "tactic_deception_suspected": detect_deception_suspected(cn),
            "tactic_incremental_concessions": detect_incremental_concessions(cn),
            "log_path": log_path,
            "turn": turn_key,
        }

        if contract_type == "finishing":
            jc = cn.get("judge_contract", {})
            p0_gives, p1_gives = extract_finishing_transfers(jc)
            row["p0_gives"] = p0_gives
            row["p1_gives"] = p1_gives
            row["transfer_pattern"] = classify_transfer_pattern(
                p0_gives if p0_gives is not None else 0,
                p1_gives if p1_gives is not None else 0,
            )

        dominant = "None"
        priority = [
            "tactic_no_deal_walkaway",
            "tactic_take_it_or_leave_it",
            "tactic_anchoring",
            "tactic_power_asymmetry",
            "tactic_incremental_concessions",
            "tactic_mutual_verification",
            "tactic_path_analysis",
            "tactic_deception_suspected",
        ]
        for tactic in priority:
            if row[tactic]:
                dominant = TACTIC_DISPLAY[tactic]
                break
        row["dominant_tactic"] = dominant

        for player_idx in range(2):
            p_msgs = get_player_messages(cn, player_idx)
            if p_msgs:
                row[f"quote_player_{player_idx}"] = p_msgs[0][:500]

        results.append(row)

    return results


# ---------------------------------------------------------------------------
# Figure generation
# ---------------------------------------------------------------------------

def generate_tactic_heatmap(df, output_path):
    """Generate tactic frequency heatmap: models (rows) x tactics (columns)."""
    models = sorted(df["model_pair"].unique())
    tactic_labels = [TACTIC_DISPLAY[t] for t in TACTIC_COLUMNS]

    freq_data = []
    for model in models:
        model_df = df[df["model_pair"] == model]
        row = [model_df[t].mean() for t in TACTIC_COLUMNS]
        freq_data.append(row)

    fig, ax = plt.subplots(figsize=(12, max(4, len(models) * 0.8)))
    sns.heatmap(
        np.array(freq_data),
        annot=True, fmt=".0%",
        xticklabels=tactic_labels, yticklabels=models,
        cmap="YlOrRd", vmin=0, vmax=1, ax=ax, linewidths=0.5,
    )
    ax.set_title("Negotiation Tactic Frequency by Model", fontsize=14, pad=12)
    ax.set_xlabel("Tactic")
    ax.set_ylabel("Model")
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved heatmap: {output_path}")


def generate_cross_model_table(df, output_path):
    """Generate LaTeX cross-model comparison table."""
    models = sorted(df["model_pair"].unique())
    rows = []
    for model in models:
        mdf = df[df["model_pair"] == model]
        avg_msgs = mdf["conversation_length"].mean()
        agreement_rate = (mdf["agreement_status"] == "agreed").mean()

        finishing = mdf[mdf["contract_type"] == "finishing"]
        if len(finishing) > 0 and "transfer_pattern" in finishing.columns:
            pattern = finishing["transfer_pattern"].mode()
            most_common_pattern = pattern.iloc[0] if len(pattern) > 0 else "N/A"
        else:
            most_common_pattern = "N/A"

        dom = mdf["dominant_tactic"].mode()
        dominant = dom.iloc[0] if len(dom) > 0 else "N/A"

        rows.append({
            "Model": model,
            "Avg Messages": f"{avg_msgs:.1f}",
            "Agreement Rate": f"{agreement_rate:.1%}",
            "Common Finish Pattern": most_common_pattern,
            "Dominant Tactic": dominant,
        })

    rows.sort(key=lambda r: float(r["Agreement Rate"].rstrip("%")), reverse=True)

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Cross-model negotiation comparison. Agreement rates, average message counts, dominant finishing contract patterns, and most frequent negotiation tactic per model.}",
        r"\label{tab:cross_model_negotiation}",
        r"\small",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"Model & Avg Msgs & Agree Rate & Finish Pattern & Dominant Tactic \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(
            f"  {r['Model']} & {r['Avg Messages']} & {r['Agreement Rate']} "
            f"& {r['Common Finish Pattern']} & {r['Dominant Tactic']} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Saved LaTeX table: {output_path}")


def generate_point_transfer_distributions(df, output_path):
    """Generate grouped bar chart of finishing contract point transfer patterns."""
    finishing = df[df["contract_type"] == "finishing"].copy()
    if len(finishing) == 0 or "transfer_pattern" not in finishing.columns:
        print("  No finishing contract data -- skipping point transfer chart")
        return

    models = sorted(finishing["model_pair"].unique())
    buckets = ["Mutual Dependency", "Asymmetric"]
    patterns = ["(0,0)", "(0,20)", "(10,10)", "Other"]
    pattern_colors = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

    for ax_idx, bucket in enumerate(buckets):
        ax = axes[ax_idx]
        bucket_data = finishing[finishing["bucket"] == bucket]
        if len(bucket_data) == 0:
            ax.set_title(f"{bucket}\n(no data)")
            continue

        x = np.arange(len(models))
        width = 0.18

        for p_idx, pattern in enumerate(patterns):
            counts = []
            for model in models:
                model_bucket = bucket_data[bucket_data["model_pair"] == model]
                total = len(model_bucket)
                frac = (model_bucket["transfer_pattern"] == pattern).sum() / total if total > 0 else 0
                counts.append(frac)
            offset = (p_idx - 1.5) * width
            ax.bar(x + offset, counts, width, label=pattern, color=pattern_colors[p_idx])

        ax.set_title(bucket, fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(models, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Fraction of negotiations" if ax_idx == 0 else "")
        ax.set_ylim(0, 1.05)
        ax.legend(title="Transfer Pattern", fontsize=8, title_fontsize=9)

    fig.suptitle("Finishing Contract Point Transfer Distributions", fontsize=14, y=1.02)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved distributions chart: {output_path}")


# ---------------------------------------------------------------------------
# GPT-4.1 board-type and contract-type breakdown figures
# ---------------------------------------------------------------------------

def generate_gpt41_by_contract_type(df, output_path):
    """Heatmap: contract types (rows) x tactics (columns) for GPT-4.1."""
    gpt = df[df["model_pair"] == FOCUS_MODEL]
    if len(gpt) == 0:
        print(f"  No {FOCUS_MODEL} data -- skipping contract-type heatmap")
        return

    contract_types = sorted(gpt["contract_type"].unique())
    ct_labels = [CONTRACT_DISPLAY.get(c, c) for c in contract_types]
    tactic_labels = [TACTIC_DISPLAY[t] for t in TACTIC_COLUMNS]

    freq_data = []
    for ct in contract_types:
        row = [gpt[gpt["contract_type"] == ct][t].mean() for t in TACTIC_COLUMNS]
        freq_data.append(row)

    fig, ax = plt.subplots(figsize=(12, 3.5))
    sns.heatmap(
        np.array(freq_data),
        annot=True, fmt=".0%",
        xticklabels=tactic_labels, yticklabels=ct_labels,
        cmap="YlOrRd", vmin=0, vmax=1, ax=ax, linewidths=0.5,
    )
    ax.set_title(f"{FOCUS_MODEL}: Tactic Frequency by Contract Type", fontsize=13, pad=10)
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {FOCUS_MODEL} contract-type heatmap: {output_path}")


def generate_gpt41_by_board_type(df, output_path):
    """Heatmap: board types (rows) x tactics (columns) for GPT-4.1."""
    gpt = df[df["model_pair"] == FOCUS_MODEL]
    if len(gpt) == 0:
        print(f"  No {FOCUS_MODEL} data -- skipping board-type heatmap")
        return

    buckets = sorted(gpt["bucket"].unique())
    tactic_labels = [TACTIC_DISPLAY[t] for t in TACTIC_COLUMNS]

    freq_data = []
    for b in buckets:
        row = [gpt[gpt["bucket"] == b][t].mean() for t in TACTIC_COLUMNS]
        freq_data.append(row)

    fig, ax = plt.subplots(figsize=(12, 3.5))
    sns.heatmap(
        np.array(freq_data),
        annot=True, fmt=".0%",
        xticklabels=tactic_labels, yticklabels=buckets,
        cmap="YlOrRd", vmin=0, vmax=1, ax=ax, linewidths=0.5,
    )
    ax.set_title(f"{FOCUS_MODEL}: Tactic Frequency by Board Type", fontsize=13, pad=10)
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {FOCUS_MODEL} board-type heatmap: {output_path}")


def generate_gpt41_board_x_contract_grid(df, output_path, log_counts=None):
    """3x3 grid of mini bar charts: board (row) x contract (col) for GPT-4.1.

    log_counts: dict mapping (model, bucket, contract_type) -> count of log files on disk.
                Used for the n= label so it reflects total logs, not just successfully parsed ones.
    """
    gpt = df[df["model_pair"] == FOCUS_MODEL]
    if len(gpt) == 0:
        print(f"  No {FOCUS_MODEL} data -- skipping board x contract grid")
        return

    buckets = sorted(gpt["bucket"].unique())
    contract_types = sorted(gpt["contract_type"].unique())
    key_tactics = TACTIC_COLUMNS
    tactic_labels = [TACTIC_DISPLAY[t].replace(" ", "\n") for t in key_tactics]
    colors = ["#4e79a7", "#f28e2b", "#e15759", "#ff9da7", "#59a14f", "#edc948", "#b07aa1", "#76b7b2"]

    fig, axes = plt.subplots(
        len(buckets), len(contract_types),
        figsize=(16, 3.2 * len(buckets)), sharey=True,
    )

    for r, bucket in enumerate(buckets):
        for c, ct in enumerate(contract_types):
            ax = axes[r][c] if len(buckets) > 1 else axes[c]
            sub = gpt[(gpt["bucket"] == bucket) & (gpt["contract_type"] == ct)]
            n_classified = len(sub)
            freqs = [sub[t].mean() if n_classified > 0 else 0 for t in key_tactics]

            # n from log count on disk
            n_label = n_classified
            if log_counts:
                n_label = log_counts.get((FOCUS_MODEL, bucket, ct), n_classified)

            x = np.arange(len(key_tactics))
            bars = ax.bar(x, freqs, color=colors)
            ax.set_ylim(0, 1.05)
            ax.set_xticks(x)
            ax.set_xticklabels(tactic_labels, fontsize=6, ha="center")

            if r == 0:
                ax.set_title(CONTRACT_DISPLAY.get(ct, ct), fontsize=11, fontweight="bold")
            if c == 0:
                ax.set_ylabel(bucket, fontsize=10, fontweight="bold")

            ax.text(
                0.98, 0.95, f"n={n_label}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=8, color="#666",
            )

            for bar, freq in zip(bars, freqs):
                if freq > 0.02:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                        f"{freq:.0%}", ha="center", va="bottom", fontsize=7,
                    )

    fig.suptitle(
        f"{FOCUS_MODEL}: Tactic Frequency by Board Type x Contract Type",
        fontsize=14, y=1.01,
    )
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {FOCUS_MODEL} board x contract grid: {output_path}")


def generate_gpt41_conv_length_boxplot(df, output_path):
    """Box plot of conversation length for GPT-4.1 by board type x contract type."""
    gpt = df[df["model_pair"] == FOCUS_MODEL].copy()
    if len(gpt) == 0:
        print(f"  No {FOCUS_MODEL} data -- skipping conversation length boxplot")
        return

    gpt["contract_display"] = gpt["contract_type"].map(CONTRACT_DISPLAY)

    fig, ax = plt.subplots(figsize=(10, 5))
    buckets = sorted(gpt["bucket"].unique())
    cts = sorted(gpt["contract_display"].unique())
    palette = {"Asymmetric": "#e15759", "Independent": "#4e79a7", "Mutual Dependency": "#59a14f"}

    positions = []
    labels = []
    box_data = []
    box_colors = []
    pos = 0
    for ct in cts:
        for bucket in buckets:
            sub = gpt[(gpt["contract_display"] == ct) & (gpt["bucket"] == bucket)]
            if len(sub) > 0:
                box_data.append(sub["conversation_length"].values)
                box_colors.append(palette.get(bucket, "#999"))
                positions.append(pos)
                labels.append(f"{bucket}\n({ct})")
                pos += 1
        pos += 0.5

    bp = ax.boxplot(box_data, positions=positions, widths=0.6, patch_artist=True)
    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=8, rotation=30, ha="right")
    ax.set_ylabel("Conversation Length (non-system messages)")
    ax.set_title(f"{FOCUS_MODEL}: Conversation Length by Board Type and Contract Type", fontsize=12)

    from matplotlib.patches import Patch
    legend_handles = [Patch(facecolor=palette[b], alpha=0.7, label=b) for b in buckets]
    ax.legend(handles=legend_handles, fontsize=9, loc="upper right")

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {FOCUS_MODEL} conversation length boxplot: {output_path}")


# ---------------------------------------------------------------------------
# Illustrative quotes extraction
# ---------------------------------------------------------------------------

def extract_illustrative_quotes(df):
    """Extract one illustrative quote per tactic."""
    quotes = {}
    for tactic in TACTIC_COLUMNS:
        tactic_rows = df[df[tactic] == True]
        if len(tactic_rows) == 0:
            continue
        best = None
        best_len = float("inf")
        for _, row in tactic_rows.iterrows():
            q = row.get("quote_player_0", "") or row.get("quote_player_1", "")
            if q and len(q) < best_len:
                best = {
                    "tactic": TACTIC_DISPLAY[tactic],
                    "quote": q,
                    "model": row["model_pair"],
                    "bucket": row["bucket"],
                    "contract_type": row["contract_type"],
                }
                best_len = len(q)
        if best:
            quotes[tactic] = best
    return quotes


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

def print_summary(df, log_counts=None):
    """Print summary statistics to stdout."""
    print("\n" + "=" * 70)
    print("NEGOTIATION TACTICS CLASSIFICATION SUMMARY")
    print("=" * 70)

    total_logs = sum(log_counts.values()) if log_counts else "N/A"
    print(f"\nTotal logs on disk: {total_logs}")
    print(f"Negotiations classified: {len(df)}")
    print(f"Models: {sorted(df['model_pair'].unique())}")
    print(f"Contract types: {sorted(df['contract_type'].unique())}")
    print(f"Board types: {sorted(df['bucket'].unique())}")

    print("\n--- Agreement Rates by Model ---")
    for model in sorted(df["model_pair"].unique()):
        mdf = df[df["model_pair"] == model]
        rate = (mdf["agreement_status"] == "agreed").mean()
        print(f"  {model:20s}: {rate:.1%} ({len(mdf)} negotiations)")

    overall_rate = (df["agreement_status"] == "agreed").mean()
    print(f"  {'Overall':20s}: {overall_rate:.1%}")

    print("\n--- Average Conversation Length (non-system messages) ---")
    for model in sorted(df["model_pair"].unique()):
        mdf = df[df["model_pair"] == model]
        avg = mdf["conversation_length"].mean()
        print(f"  {model:20s}: {avg:.1f}")

    print("\n--- Tactic Frequencies (overall) ---")
    for tactic in TACTIC_COLUMNS:
        freq = df[tactic].mean()
        print(f"  {TACTIC_DISPLAY[tactic]:30s}: {freq:.1%}")

    print("\n--- Dominant Tactic Distribution ---")
    dom_counts = df["dominant_tactic"].value_counts()
    for tactic, count in dom_counts.items():
        print(f"  {tactic:30s}: {count:4d} ({count/len(df):.1%})")

    finishing = df[df["contract_type"] == "finishing"]
    if len(finishing) > 0 and "transfer_pattern" in finishing.columns:
        print("\n--- Finishing Contract Transfer Patterns ---")
        for model in sorted(finishing["model_pair"].unique()):
            mdf = finishing[finishing["model_pair"] == model]
            print(f"\n  {model}:")
            for bucket in sorted(mdf["bucket"].unique()):
                bdf = mdf[mdf["bucket"] == bucket]
                pattern_counts = bdf["transfer_pattern"].value_counts()
                print(f"    {bucket}:")
                for pattern, count in pattern_counts.items():
                    print(f"      {pattern}: {count} ({count/len(bdf):.0%})")


# ---------------------------------------------------------------------------
# HTML review page generation
# ---------------------------------------------------------------------------

def generate_review_html(df, quotes, figures_dir, output_path, log_counts=None):
    """Generate a self-contained HTML review page."""
    import base64

    def embed_image(path):
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        ext = Path(path).suffix.lstrip(".")
        if ext == "pdf":
            return f'<embed src="data:application/pdf;base64,{data}" type="application/pdf" width="100%" height="600px"/>'
        return f'<img src="data:image/{ext};base64,{data}" style="max-width:100%;"/>'

    table_tex_path = os.path.join(figures_dir, "cross_model_comparison_table.tex")
    table_tex = ""
    if os.path.exists(table_tex_path):
        with open(table_tex_path) as f:
            table_tex = f.read()

    models = sorted(df["model_pair"].unique())
    agreement_rates = {}
    avg_msgs = {}
    for model in models:
        mdf = df[df["model_pair"] == model]
        agreement_rates[model] = (mdf["agreement_status"] == "agreed").mean()
        avg_msgs[model] = mdf["conversation_length"].mean()

    overall_rate = (df["agreement_status"] == "agreed").mean()
    total_logs = sum(log_counts.values()) if log_counts else len(df)

    tactic_rows_html = ""
    for tactic in TACTIC_COLUMNS:
        freq = df[tactic].mean()
        tactic_rows_html += f"<tr><td>{TACTIC_DISPLAY[tactic]}</td><td>{freq:.1%}</td></tr>\n"

    model_rows_html = ""
    for model in models:
        model_rows_html += f"<tr><td>{model}</td><td>{agreement_rates[model]:.1%}</td><td>{avg_msgs[model]:.1f}</td></tr>\n"

    quotes_html = ""
    for tactic_key, q in quotes.items():
        quotes_html += f"""
        <div class="quote-card">
            <h4>{q['tactic']}</h4>
            <blockquote>{q['quote'][:400]}</blockquote>
            <p class="meta">Model: {q['model']} | Board: {q['bucket']} | Contract: {q['contract_type']}</p>
        </div>"""

    tactic_descriptions = {
        "Anchoring": "The first proposal contains extreme asymmetry -- one player opens with a demand for 16+ points or a 3:1+ tile ratio, setting an aggressive anchor for the negotiation.",
        "Take-it-or-leave-it": "Agreement is reached in 3 or fewer non-system messages. The proposer makes a single offer that is accepted without substantive counter-proposals.",
        "No-deal Walk-away": "Negotiation ends without agreement. Players reject the proposed contract or explicitly state they do not need cooperation.",
        "Power Asymmetry Exploitation": "A player explicitly leverages their structural advantage, using language like 'I can reach my goal without you' or 'you need me more than I need you.'",
        "Mutual Verification": "Both players engage in coordinated verification of tile positions, chip costs, and path feasibility, using words like 'verify,' 'confirm,' or 'check' alongside coordinate references.",
        "Path Analysis": "Players present detailed path calculations using arrow notation (e.g., (0,0) -> (1,0) -> ...) or enumerate chip costs for specific routes.",
        "Deception (suspected)": "A player states chip counts inconsistent with earlier claims or reverses agreed terms during the agreement phase. Flagged for manual review.",
        "Incremental Concessions": "Extended negotiation (6+ messages) with multiple numeric proposals showing progressively smaller gaps, indicating gradual convergence toward a deal.",
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Negotiation Tactics Analysis Review</title>
<style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 1100px; margin: 0 auto; padding: 20px; background: #fafafa; color: #333; }}
    h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
    h2 {{ color: #16213e; margin-top: 40px; border-bottom: 1px solid #ddd; padding-bottom: 6px; }}
    h3 {{ color: #0f3460; }}
    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #16213e; color: white; }}
    tr:nth-child(even) {{ background: #f2f2f2; }}
    .figure-container {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 20px 0; }}
    .figure-container h3 {{ margin-top: 0; }}
    .quote-card {{ background: white; border-left: 4px solid #0f3460; padding: 12px 20px; margin: 12px 0; border-radius: 0 8px 8px 0; }}
    .quote-card h4 {{ margin: 0 0 8px 0; color: #0f3460; }}
    .quote-card blockquote {{ margin: 0; padding: 10px; background: #f8f9fa; border-radius: 4px; font-style: italic; white-space: pre-wrap; word-wrap: break-word; font-size: 0.9em; }}
    .quote-card .meta {{ font-size: 0.8em; color: #666; margin-top: 6px; }}
    .stat {{ font-size: 1.2em; font-weight: bold; color: #0f3460; }}
    .latex-block {{ background: #f8f9fa; border: 1px solid #ddd; border-radius: 4px; padding: 15px; font-family: monospace; font-size: 0.85em; white-space: pre-wrap; overflow-x: auto; }}
    .tactic-desc {{ margin: 8px 0 20px 20px; color: #555; }}
    .overview-box {{ background: #e8f0fe; border-radius: 8px; padding: 20px; margin: 20px 0; }}
</style>
</head>
<body>

<h1>Negotiation Tactics Analysis -- Review</h1>

<div class="overview-box">
<h2 style="margin-top:0; border:none;">1. Overview</h2>
<p>This page presents all proposed additions to the paper's "Qualitative Contract Formation" section.</p>
<ul>
    <li><strong>Tactics taxonomy</strong>: 8 heuristic categories for classifying negotiation behavior</li>
    <li><strong>7 figures/tables</strong>: cross-model heatmap, comparison table, point transfer distributions, + 4 GPT-4.1 breakdowns</li>
    <li><strong>Illustrative quotes</strong>: one representative quote per tactic from the logs</li>
</ul>
<p>Total logs on disk: <span class="stat">{total_logs}</span> |
   Negotiations classified: <span class="stat">{len(df)}</span> |
   Overall agreement rate: <span class="stat">{overall_rate:.1%}</span> |
   Models: <span class="stat">{len(models)}</span></p>
</div>

<h2>2. Cross-Model Figures</h2>

<div class="figure-container">
<h3>Figure: Tactic Frequency Heatmap</h3>
<p>Fraction of negotiations where each tactic was detected, by model.</p>
{embed_image(os.path.join(figures_dir, 'tactic_frequency_heatmap.png'))}
</div>

<div class="figure-container">
<h3>Figure: Point Transfer Distributions</h3>
<p>Finishing contract point transfer patterns per model, split by board type.</p>
{embed_image(os.path.join(figures_dir, 'point_transfer_distributions.png'))}
</div>

<div class="figure-container">
<h3>Table: Cross-Model Comparison (LaTeX)</h3>
<div class="latex-block">{table_tex}</div>
</div>

<h2>3. {FOCUS_MODEL} Breakdown: Board Type and Contract Type</h2>

<div class="figure-container">
<h3>{FOCUS_MODEL}: Tactics by Contract Type</h3>
{embed_image(os.path.join(figures_dir, 'gpt41_tactics_by_contract.png'))}
</div>

<div class="figure-container">
<h3>{FOCUS_MODEL}: Tactics by Board Type</h3>
{embed_image(os.path.join(figures_dir, 'gpt41_tactics_by_board.png'))}
</div>

<div class="figure-container">
<h3>{FOCUS_MODEL}: Board Type x Contract Type Grid</h3>
<p>n= values are log file counts on disk (total games run for that combination).</p>
{embed_image(os.path.join(figures_dir, 'gpt41_board_x_contract_grid.png'))}
</div>

<div class="figure-container">
<h3>{FOCUS_MODEL}: Conversation Length Distribution</h3>
{embed_image(os.path.join(figures_dir, 'gpt41_conv_length_boxplot.png'))}
</div>
"""

    # GPT-4.1 detailed table
    gpt_df = df[df["model_pair"] == FOCUS_MODEL]
    if len(gpt_df) > 0:
        gpt_detail_html = "<table><tr><th>Board Type</th><th>Contract Type</th><th>n (logs)</th><th>n (classified)</th><th>Agreement Rate</th><th>Avg Messages</th><th>Most Common Tactic</th></tr>\n"
        for bucket in sorted(gpt_df["bucket"].unique()):
            for ct in sorted(gpt_df["contract_type"].unique()):
                sub = gpt_df[(gpt_df["bucket"] == bucket) & (gpt_df["contract_type"] == ct)]
                if len(sub) == 0:
                    continue
                n_logs = log_counts.get((FOCUS_MODEL, bucket, ct), "?") if log_counts else "?"
                rate = (sub["agreement_status"] == "agreed").mean()
                avg_m = sub["conversation_length"].mean()
                dom = sub["dominant_tactic"].mode()
                dom_str = dom.iloc[0] if len(dom) > 0 else "N/A"
                gpt_detail_html += f"<tr><td>{bucket}</td><td>{CONTRACT_DISPLAY.get(ct, ct)}</td><td>{n_logs}</td><td>{len(sub)}</td><td>{rate:.1%}</td><td>{avg_m:.1f}</td><td>{dom_str}</td></tr>\n"
        gpt_detail_html += "</table>"

        html += f"""
<h3>{FOCUS_MODEL}: Detailed Board x Contract Summary</h3>
{gpt_detail_html}
"""

    html += f"""
<h2>4. Tactics Taxonomy</h2>
"""
    for tactic_key in TACTIC_COLUMNS:
        name = TACTIC_DISPLAY[tactic_key]
        desc = tactic_descriptions.get(name, "")
        freq = df[tactic_key].mean()
        html += f"""<p><strong>{name}</strong> (detected in {freq:.1%} of negotiations)</p>
<p class="tactic-desc">{desc}</p>
"""

    html += f"""
<h3>Cross-Model Summary</h3>
<table>
<tr><th>Model</th><th>Agreement Rate</th><th>Avg Messages</th></tr>
{model_rows_html}
</table>

<h3>Overall Tactic Frequencies</h3>
<table>
<tr><th>Tactic</th><th>Frequency</th></tr>
{tactic_rows_html}
</table>

<h2>5. Illustrative Quotes</h2>
{quotes_html}

<h2>6. Classification Methodology</h2>
<p>All tactics are classified using deterministic heuristics (keyword and pattern matching on negotiation transcripts). No LLM calls are used for classification. Each log file is parsed from <code>game.turns.&lt;N&gt;.contract_negotiation</code>, which contains two conversation histories (one per player) and the final agreement/contract.</p>

<h3>Anchoring</h3>
<p>Examines only the <strong>first assistant message</strong> in the negotiation.</p>
<ul>
    <li><strong>Finishing contracts:</strong> Triggered if any number between 16 and 20 appears near keywords ("point", "give", "transfer", "pay", "receive"), or if an explicit 0/20 pattern is found.</li>
    <li><strong>Strict contracts:</strong> Triggered if the first proposal mentions tile/chip/resource counts in a ratio of 3:1 or greater.</li>
</ul>

<h3>Take-it-or-leave-it</h3>
<p><code>agreement_status == True</code> AND total non-system messages in the conversation &lt;= 3.</p>

<h3>No-deal Walk-away</h3>
<p>Any of:</p>
<ul>
    <li><code>agreement_status == False</code></li>
    <li>Parsed agreement response has status "rejected" or "disagreed"</li>
    <li>Finishing contract with (0,0) transfer AND messages contain refusal phrases: "don't need", "no cooperation", "refuse", "won't cooperate", "not interested"</li>
</ul>

<h3>Power Asymmetry Exploitation</h3>
<p>All non-system messages (both players) are searched for any of these phrases:</p>
<p style="font-family: monospace; font-size: 0.85em; background: #f8f9fa; padding: 10px; border-radius: 4px;">
"i can reach my goal without" | "i don't need you" | "you cannot reach" | "you can't reach" | "you need me" | "self-sufficient" | "independently" | "without any help" | "without your help" | "don't need cooperation" | "without assistance" | "reach my goal on my own"
</p>

<h3>Mutual Verification</h3>
<p>Both players must independently satisfy two conditions in their own assistant messages:</p>
<ol>
    <li>At least one coordinate reference matching the pattern <code>(digit, digit)</code></li>
    <li>At least one verification word: "verify", "confirm", "check", "correct", "recalculate", "double-check"</li>
</ol>
<p>The tactic is only flagged if <em>both</em> players meet both conditions.</p>

<h3>Path Analysis</h3>
<p>Searches all non-system messages for either:</p>
<ul>
    <li>Arrow notation: <code>(x,y) -&gt; (x,y)</code> (two or more coordinates connected by arrows)</li>
    <li>4+ coordinate references AND at least one cost keyword ("cost", "chip", "spend", "require", "need", "use")</li>
</ul>

<h3>Deception (suspected)</h3>
<p>Flagged for manual review if either:</p>
<ul>
    <li>Reversal language appears: "actually, i changed my mind", "let me revise", "on second thought", "i lied", "that's not true", "i was bluffing"</li>
    <li>A player claims different chip counts for the same color at different points (e.g., "i have 5 red" then later "i have 3 red")</li>
</ul>

<h3>Incremental Concessions</h3>
<p>Requires all of:</p>
<ol>
    <li>&gt;= 6 non-system messages in the conversation</li>
    <li>Extract all numbers 0-20 from each message (taking the max per message as the "proposal")</li>
    <li>Compute gaps between consecutive proposals; at least 2 instances where the gap decreases (indicating convergence)</li>
</ol>

<h3>Dominant Tactic</h3>
<p>Each negotiation is assigned a single "dominant tactic" using a fixed priority order: No-deal Walk-away &gt; Take-it-or-leave-it &gt; Anchoring &gt; Power Asymmetry &gt; Incremental Concessions &gt; Mutual Verification &gt; Path Analysis &gt; Deception. The first matching tactic wins. Multiple tactics can be true simultaneously; the dominant tactic is just the highest-priority one.</p>

<h3>Limitations</h3>
<ul>
    <li>All heuristics are keyword-based, so they can produce false positives (e.g., "independently" in a non-leverage context) and false negatives (e.g., anchoring phrased without the expected keywords).</li>
    <li>The "Deception" classifier is particularly coarse -- inconsistent chip counts may reflect legitimate recalculation rather than deception.</li>
    <li>Incremental Concessions relies on number extraction that doesn't distinguish point proposals from other numeric references (e.g., coordinates, chip counts).</li>
</ul>

<p>Full source: <code>analysis/classify_negotiation_tactics.py</code></p>

<h2>7. Data Summary</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Total logs on disk</td><td>{total_logs}</td></tr>
<tr><td>Negotiations classified</td><td>{len(df)}</td></tr>
<tr><td>Overall agreement rate</td><td>{overall_rate:.1%}</td></tr>
<tr><td>Models</td><td>{', '.join(models)}</td></tr>
<tr><td>Contract types</td><td>{', '.join(sorted(df['contract_type'].unique()))}</td></tr>
<tr><td>Board types</td><td>{', '.join(sorted(df['bucket'].unique()))}</td></tr>
</table>

<hr>
<p style="color:#999; font-size:0.85em;">Generated by analysis/classify_negotiation_tactics.py</p>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"  Saved review HTML: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Classify negotiation tactics from verbose logs")
    parser.add_argument(
        "--logs-dir",
        nargs="+",
        default=["public_logs/reduced_config_runs"],
        help="Directories containing verbose log files",
    )
    parser.add_argument("--output-dir", default="analysis", help="Output directory for CSV and figures")
    parser.add_argument("--figures-dir", default=None, help="Output directory for figures (default: OUTPUT_DIR/figures)")
    parser.add_argument("--overleaf-dir", default="/tmp/overleaf_source", help="Overleaf source directory")
    parser.add_argument("--html-only", action="store_true", help="Skip classification, just regenerate HTML from existing CSV")
    args = parser.parse_args()

    figures_dir = args.figures_dir or os.path.join(args.output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    csv_path = os.path.join(args.output_dir, "negotiation_tactics.csv")
    log_counts_path = os.path.join(args.output_dir, "log_counts.json")

    if args.html_only:
        if not os.path.exists(csv_path):
            print(f"ERROR: {csv_path} not found. Run without --html-only first.")
            sys.exit(1)
        df = pd.read_csv(csv_path)
    else:
        print("Finding verbose logs...")
        log_paths = find_verbose_logs(args.logs_dir)
        print(f"Found {len(log_paths)} verbose log files")

        # Filter to contract negotiations only
        contract_logs = [
            p for p in log_paths
            if "contract_none" not in p
            and ("contract_for_finishing" in p or "contract_strict" in p or "contract_tile_with_judge" in p)
        ]
        print(f"Logs with contract negotiations: {len(contract_logs)}")

        # Count logs per group from paths (ground truth n)
        log_counts_raw = count_logs_by_group(contract_logs)
        with open(log_counts_path, "w") as f:
            json.dump({str(k): v for k, v in log_counts_raw.items()}, f, indent=2)
        print(f"Log counts saved: {log_counts_path}")

        print("Classifying negotiations...")
        all_results = []
        for i, log_path in enumerate(contract_logs):
            results = classify_negotiation(log_path)
            all_results.extend(results)
            if (i + 1) % 500 == 0:
                print(f"  Processed {i + 1}/{len(contract_logs)} logs ({len(all_results)} negotiations so far)")

        if not all_results:
            print("ERROR: No negotiations found in logs.")
            sys.exit(1)

        df = pd.DataFrame(all_results)
        save_cols = [
            "model_pair", "bucket", "grid_id", "contract_type",
            "agreement_status", "conversation_length",
        ] + TACTIC_COLUMNS + ["dominant_tactic"]
        if "transfer_pattern" in df.columns:
            save_cols.extend(["p0_gives", "p1_gives", "transfer_pattern"])
        for qc in ("quote_player_0", "quote_player_1"):
            if qc in df.columns:
                save_cols.append(qc)
        df[save_cols].to_csv(csv_path, index=False)
        print(f"\nSaved CSV: {csv_path} ({len(df)} rows)")

    # Load log counts
    log_counts = None
    if os.path.exists(log_counts_path):
        with open(log_counts_path) as f:
            raw = json.load(f)
        log_counts = {}
        for k, v in raw.items():
            try:
                key = tuple(eval(k))
                log_counts[key] = v
            except Exception:
                log_counts[k] = v

    print_summary(df, log_counts)

    # Generate figures
    print("\nGenerating figures...")
    for ext in ("pdf", "png"):
        generate_tactic_heatmap(df, os.path.join(figures_dir, f"tactic_frequency_heatmap.{ext}"))
    generate_cross_model_table(df, os.path.join(figures_dir, "cross_model_comparison_table.tex"))
    for ext in ("pdf", "png"):
        generate_point_transfer_distributions(df, os.path.join(figures_dir, f"point_transfer_distributions.{ext}"))

    print(f"\nGenerating {FOCUS_MODEL} breakdown figures...")
    for ext in ("pdf", "png"):
        generate_gpt41_by_contract_type(df, os.path.join(figures_dir, f"gpt41_tactics_by_contract.{ext}"))
        generate_gpt41_by_board_type(df, os.path.join(figures_dir, f"gpt41_tactics_by_board.{ext}"))
        generate_gpt41_board_x_contract_grid(df, os.path.join(figures_dir, f"gpt41_board_x_contract_grid.{ext}"), log_counts=log_counts)
        generate_gpt41_conv_length_boxplot(df, os.path.join(figures_dir, f"gpt41_conv_length_boxplot.{ext}"))

    # Copy figures to overleaf if directory exists
    overleaf_figures = os.path.join(args.overleaf_dir, "figures")
    if os.path.isdir(overleaf_figures):
        import shutil
        table_path = os.path.join(figures_dir, "cross_model_comparison_table.tex")
        pdf_figs = [
            "tactic_frequency_heatmap.pdf",
            "point_transfer_distributions.pdf",
            "gpt41_tactics_by_contract.pdf",
            "gpt41_tactics_by_board.pdf",
            "gpt41_board_x_contract_grid.pdf",
            "gpt41_conv_length_boxplot.pdf",
        ]
        for fname in pdf_figs:
            src = os.path.join(figures_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(overleaf_figures, fname))
                print(f"  Copied {fname} to {overleaf_figures}/")
        if os.path.exists(table_path):
            shutil.copy2(table_path, os.path.join(args.overleaf_dir, "cross_model_comparison_table.tex"))
            print(f"  Copied cross_model_comparison_table.tex to {args.overleaf_dir}/")

    # Extract quotes and generate HTML
    quotes = extract_illustrative_quotes(df)
    print(f"\nExtracted {len(quotes)} illustrative quotes")

    html_path = os.path.join(args.output_dir, "negotiation_analysis_review.html")
    generate_review_html(df, quotes, figures_dir, html_path, log_counts=log_counts)

    print("\nDone!")
    return df, quotes


if __name__ == "__main__":
    main()
