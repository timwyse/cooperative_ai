"""Classify contract-negotiation dialogues by tactic, per role, via OpenAI.

Walks public_logs/reduced_config_runs/, finds verbose_log_grid_*.json files
(excluding paths containing 'contract_none'), strips system prompt + judge
restatement, sends each dialogue to an OpenAI model with a strict JSON schema,
and writes one JSONL line per file with metadata + per-role tactic booleans
+ short evidence quotes.

Run with --random-sample 10 first to validate the prompt before sweeping all
files.
"""

import argparse
import json
import os
import random
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError

load_dotenv(override=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "public_logs" / "reduced_config_runs"
DEFAULT_OUTPUT = REPO_ROOT / "analysis" / "contract_transcripts" / "negotiation_classifications.jsonl"
DEFAULT_SAMPLE_OUTPUT = REPO_ROOT / "analysis" / "contract_transcripts" / "negotiation_classifications.sample.jsonl"

PATH_RE = re.compile(
    r"reduced_config_runs/(?P<model>[^/]+)/(?P<board_type>[^/]+)/grid_(?P<grid_id>\d+)"
    r"/ctx1_fog(?P<fog>\d{2})_p4p(?P<p4p>true|false)_contract_(?P<contract_type>.+?)_selfish(?P<selfish>\d+)"
    r"/[^/]+/verbose_log_grid_\d+_[^/]+\.json$"
)

# Ordered list of (key, display_name, role-neutral definition).
# Keep this stable — it defines both the JSON schema and the system prompt.
TACTICS = [
    ("extreme_opening_demand", "Extreme opening demand",
     "Opens with a highly lopsided offer to anchor the negotiation."),
    ("incremental_concessions", "Incremental concessions",
     "Makes small step-wise concessions across turns (may converge to a midpoint or cascade toward 0)."),
    ("power_exploitation", "Power exploitation",
     "Explicitly argues that the other player depends more on them, or that their cooperation is more valuable, to justify a better deal."),
    ("detailed_tile_by_tile_calculation", "Detailed tile-by-tile calculation",
     "Produces explicit per-tile bookkeeping of chips/costs to justify or compute an offer."),
    ("deadline_urgency_pressure", "Deadline / urgency pressure",
     "Invokes time or turn limits ('we only have N turns left') to force acceptance."),
    ("take_it_or_leave_it_ultimatum", "Take-it-or-leave-it ultimatum",
      "Presents an offer as final, non-negotiable, or threatens to withdraw cooperation if rejected."),
    ("appeal_to_fairness_norms", "Appeal to fairness / norms",
     "Invokes balance, equal splits, or 'fairness' to justify their position."),
    ("mutual_verification", "Mutual Verification",
     "Engages in coordinated verification of tile positions, chip costs, or path feasibility of the other player — using verify/confirm/check language alongside coordinate references."),
    ("refusal_to_engage", "Refusal / non-engagement",
     "Declines to negotiate meaningfully, repeats rejection, or refuses all offers without counterproposal."),
    ("guilt_or_social_pressure", "Guilt / social pressure",
     "Uses language implying selfishness, unfairness, blame, or moral criticism to pressure concessions."),
]

SYSTEM_PROMPT = (
    "You are an expert annotator of multi-agent negotiation dialogues from the Coloured Trails environment. "
    "You will be given a contract-negotiation transcript between two players: one writes as USER, the other as ASSISTANT. "
    "Classify, INDEPENDENTLY for each role, whether each of the following negotiation tactics appears in their turns. "
    "Err on the side of FALSE when ambiguous — only mark TRUE when the behaviour is clearly present.\n\n"
    "Tactic definitions (the same definition applies to both USER and ASSISTANT — you decide per role):\n"
    + "\n".join(f"- {name} ({key}): {defn}" for key, name, defn in TACTICS)
    + "\n\nFor every tactic, output four fields:\n"
      "  observed_for_user (bool), observed_for_assistant (bool),\n"
      "  evidence_user (short quote from a USER turn demonstrating the tactic or a brief synopsis demonstrating the tactic if observed_for_user is true; otherwise empty string),\n"
      "  evidence_assistant (same idea for ASSISTANT; otherwise empty string).\n"
      "Use the structured JSON schema provided. Do not include any text outside the JSON."
)


def build_schema() -> dict:
    tactic_props = {}
    for key, _, _ in TACTICS:
        tactic_props[key] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["observed_for_user", "observed_for_assistant", "evidence_user", "evidence_assistant"],
            "properties": {
                "observed_for_user": {"type": "boolean"},
                "observed_for_assistant": {"type": "boolean"},
                "evidence_user": {"type": "string"},
                "evidence_assistant": {"type": "string"},
            },
        }
    return {
        "name": "negotiation_tactics",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [k for k, _, _ in TACTICS],
            "properties": tactic_props,
        },
    }


def event_log_path_for(verbose_path: Path) -> Path:
    """Sibling event_log file: same directory, name with verbose_ → event_."""
    return verbose_path.with_name(verbose_path.name.replace("verbose_log_", "event_log_", 1))


def has_final_state(event_path: Path) -> bool:
    """A run only counts as 'completed' if its event_log has game.final_state."""
    try:
        with event_path.open() as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    return "final_state" in (data.get("game") or {})


def find_files(input_dir: Path) -> list[Path]:
    """Yield verbose_log paths whose run completed (event_log has game.final_state)."""
    files: list[Path] = []
    skipped_incomplete = 0
    skipped_missing_event = 0
    for p in input_dir.rglob("verbose_log_grid_*.json"):
        if "contract_none" in str(p):
            continue
        ev = event_log_path_for(p)
        if not ev.exists():
            skipped_missing_event += 1
            continue
        if not has_final_state(ev):
            skipped_incomplete += 1
            continue
        files.append(p)
    if skipped_incomplete or skipped_missing_event:
        print(f"  (skipped {skipped_incomplete} runs without game.final_state, "
              f"{skipped_missing_event} without event_log)", file=sys.stderr)
    return files


def parse_metadata(path: Path) -> dict | None:
    rel = str(path.relative_to(REPO_ROOT)) if path.is_absolute() else str(path)
    m = PATH_RE.search(rel.replace(os.sep, "/"))
    if not m:
        return None
    d = m.groupdict()
    if d["contract_type"] == "none":
        return None
    return {
        "model": d["model"],
        "board_type": d["board_type"],
        "grid_id": int(d["grid_id"]),
        "contract_type": d["contract_type"],
        "pay4partner": d["p4p"] == "true",
        "fog": d["fog"],
        "selfish": d["selfish"],
    }


def preprocess_conversation(conv: list[dict]) -> tuple[str, int]:
    """Strip leading system message and trailing judge restatement; return formatted block + count."""
    msgs = list(conv)
    while msgs and msgs[0].get("role") == "system":
        msgs.pop(0)
    if msgs and msgs[-1].get("content", "").lstrip().startswith("This is a summary of the contract"):
        msgs.pop()

    user_turn = 0
    asst_turn = 0
    lines = []
    for m in msgs:
        role = m.get("role", "?")
        content = (m.get("content") or "").strip()
        if role == "user":
            user_turn += 1
            lines.append(f"[USER, turn {user_turn}]:\n{content}")
        elif role == "assistant":
            asst_turn += 1
            lines.append(f"[ASSISTANT, turn {asst_turn}]:\n{content}")
        else:
            lines.append(f"[{role.upper()}]:\n{content}")
    return "\n\n".join(lines), len(msgs)


def load_existing_filepaths(output_path: Path, retry_errors: bool) -> set[str]:
    if not output_path.exists():
        return set()
    done = set()
    with output_path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            fp = row.get("filepath")
            if not fp:
                continue
            if retry_errors and row.get("error"):
                continue
            done.add(fp)
    return done


def call_openai(client: OpenAI, model: str, transcript: str, schema: dict, max_attempts: int = 3):
    last_err = None
    for attempt in range(max_attempts):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"NEGOTIATION TRANSCRIPT:\n\n{transcript}"},
                ],
                response_format={"type": "json_schema", "json_schema": schema},
            )
            return resp
        except (RateLimitError, APIConnectionError, APITimeoutError) as e:
            last_err = e
            time.sleep(min(60, 2 ** attempt + random.random()))
    raise last_err  # type: ignore[misc]


def classify_one(path: Path, client: OpenAI, model: str, schema: dict) -> dict:
    rel = str(path.relative_to(REPO_ROOT))
    base = {"filepath": rel, "tactics": None, "usage": None, "error": None}

    meta = parse_metadata(path)
    if meta is None:
        base["error"] = "path_regex_no_match"
        return base
    base.update(meta)

    try:
        with path.open() as f:
            data = json.load(f)
        cn = data["game"]["turns"]["0"]["contract_negotiation"]
        conv = cn.get("conversation_history_0")
        if not conv:
            base["error"] = "missing_conversation_history_0"
            return base

        transcript, n_msgs = preprocess_conversation(conv)
        base["n_messages_classified"] = n_msgs
        base["agreement_status"] = cn.get("agreement_status")
        base["agreement_from_player_0"] = cn.get("agreement_from_player_0")
        base["agreement_from_player_1"] = cn.get("agreement_from_player_1")

        if not transcript.strip():
            base["error"] = "empty_transcript_after_strip"
            return base

        resp = call_openai(client, model, transcript, schema)
        content = resp.choices[0].message.content
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            base["error"] = f"json_decode_error: {e}"
            base["raw_response"] = content[:1000]
            return base

        base["tactics"] = parsed
        usage = resp.usage
        cached = 0
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        base["usage"] = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cached_prompt_tokens": cached,
        }
    except Exception as e:
        base["error"] = f"{type(e).__name__}: {e}"
    return base


def write_row(out_f, lock: threading.Lock, row: dict) -> None:
    with lock:
        out_f.write(json.dumps(row) + "\n")
        out_f.flush()


def print_summary(rows: list[dict]) -> None:
    n = len(rows)
    if n == 0:
        print("No rows.")
        return
    ok = [r for r in rows if r.get("error") is None and r.get("tactics")]
    err = [r for r in rows if r.get("error") is not None]

    total_in = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in ok)
    total_out = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in ok)
    total_cached = sum((r.get("usage") or {}).get("cached_prompt_tokens", 0) for r in ok)
    # gpt-5-mini pricing as of writing: $0.15/1M input ($0.075 cached), $0.60/1M output
    cost = (total_in - total_cached) * 0.25e-6 + total_cached * 0.025e-6 + total_out * 2.0e-6

    print()
    print("=" * 70)
    print(f"Classification summary  ({n} rows: {len(ok)} ok, {len(err)} errored)")
    print("=" * 70)
    print(f"Tokens — prompt: {total_in:,}  (cached: {total_cached:,})  completion: {total_out:,}")
    print(f"Estimated cost (gpt-5-mini pricing): ${cost:.4f}")
    if err:
        err_kinds = Counter((r.get("error") or "")[:60] for r in err)
        print(f"Top error kinds: {err_kinds.most_common(5)}")

    print()
    print("Per-tactic prevalence (over successful rows):")
    print(f"  {'tactic':40s} {'user':>10s} {'assistant':>12s} {'either':>10s}")
    n_ok = len(ok) or 1
    for key, name, _ in TACTICS:
        cu = sum(1 for r in ok if r["tactics"][key]["observed_for_user"])
        ca = sum(1 for r in ok if r["tactics"][key]["observed_for_assistant"])
        ce = sum(1 for r in ok if r["tactics"][key]["observed_for_user"] or r["tactics"][key]["observed_for_assistant"])
        print(f"  {name[:40]:40s} {cu:5d} ({100*cu/n_ok:4.1f}%) {ca:5d} ({100*ca/n_ok:4.1f}%) {ce:5d} ({100*ce/n_ok:4.1f}%)")

    print()
    print("Cross-tab: % rows with tactic observed (either role) by (model × contract_type):")
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in ok:
        cells[(r["model"], r["contract_type"])].append(r)
    header = f"  {'(model, contract_type)':50s} {'N':>5s}  " + "  ".join(k[:6] for k, _, _ in TACTICS)
    print(header)
    for (mdl, ct), group in sorted(cells.items()):
        ng = len(group)
        cells_str = []
        for key, _, _ in TACTICS:
            c = sum(1 for r in group if r["tactics"][key]["observed_for_user"] or r["tactics"][key]["observed_for_assistant"])
            cells_str.append(f"{100*c/ng:5.1f}")
        print(f"  {(mdl[:30] + ', ' + ct[:18])[:50]:50s} {ng:5d}  " + "  ".join(cells_str))


def main() -> int:
    p = argparse.ArgumentParser(description="Classify contract-negotiation dialogues by tactic via OpenAI.")
    p.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    p.add_argument("--output", type=Path, default=None,
                   help="JSONL output path. Default: full-run path or .sample.jsonl in --random-sample mode.")
    p.add_argument("--model", default="gpt-5-mini")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--random-sample", type=int, default=None,
                   help="If set, randomly sample this many files and write to .sample.jsonl. Skips resume.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=None, help="Cap total files (for testing).")
    p.add_argument("--retry-errors", action="store_true", help="Re-attempt rows where error is set.")
    args = p.parse_args()

    start_time = time.time()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in environment / .env", file=sys.stderr)
        return 2

    if args.output is None:
        args.output = DEFAULT_SAMPLE_OUTPUT if args.random_sample else DEFAULT_OUTPUT
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {args.input_dir} ...", file=sys.stderr)
    all_files = find_files(args.input_dir)
    print(f"Found {len(all_files)} non-contract_none log files.", file=sys.stderr)
    if not all_files:
        return 1

    sample_mode = args.random_sample is not None
    if sample_mode:
        rng = random.Random(args.seed)
        rng.shuffle(all_files)
        all_files = all_files[: args.random_sample]
        print(f"Sampled {len(all_files)} files (seed={args.seed}). Writing to {args.output}.", file=sys.stderr)
        # Truncate sample output for fresh runs.
        args.output.write_text("")
        done = set()
    else:
        done = load_existing_filepaths(args.output, args.retry_errors)
        if done:
            print(f"Resume: {len(done)} already-classified files will be skipped.", file=sys.stderr)
            if args.retry_errors:
                # Rewrite output without errored rows so they can be redone cleanly.
                kept = []
                with args.output.open() as f:
                    for line in f:
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not row.get("error"):
                            kept.append(line)
                args.output.write_text("".join(kept))

    todo = [f for f in all_files if str(f.relative_to(REPO_ROOT)) not in done]
    if args.limit is not None:
        todo = todo[: args.limit]
    print(f"Starting classification. Start time: {time.ctime(start_time)}", file=sys.stderr)
    print(f"To classify: {len(todo)} files. Model={args.model}, workers={args.workers}.", file=sys.stderr)
    if not todo:
        print("Nothing to do.", file=sys.stderr)
        return 0

    schema = build_schema()
    client = OpenAI(api_key=api_key)

    new_rows: list[dict] = []
    write_lock = threading.Lock()
    counter_lock = threading.Lock()
    state = {"done": 0, "errs": 0, "next_print": 10}
    t0 = time.time()

    with args.output.open("a") as out_f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(classify_one, path, client, args.model, schema): path for path in todo}
        for fut in as_completed(futures):
            try:
                row = fut.result()
            except Exception as e:
                path = futures[fut]
                row = {"filepath": str(path.relative_to(REPO_ROOT)), "error": f"{type(e).__name__}: {e}",
                       "tactics": None, "usage": None}
            write_row(out_f, write_lock, row)
            new_rows.append(row)
            with counter_lock:
                state["done"] += 1
                if row.get("error"):
                    state["errs"] += 1
                if state["done"] >= state["next_print"] or state["done"] == len(todo):
                    elapsed = time.time() - t0
                    rate = state["done"] / max(elapsed, 1e-6)
                    eta = (len(todo) - state["done"]) / max(rate, 1e-6)
                    print(f"  [{state['done']}/{len(todo)}] errs={state['errs']}  "
                          f"rate={rate:.1f}/s  eta={eta/60:.1f}m", file=sys.stderr)
                    state["next_print"] = min(state["done"] + max(10, len(todo) // 50), len(todo))

    # Combine with previously-written rows for a complete summary.
    all_rows: list[dict] = []
    with args.output.open() as f:
        for line in f:
            try:
                all_rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print_summary(all_rows)
    print(f"\nWrote {args.output}", file=sys.stderr)
    print(f"Total elapsed time: {(time.time() - start_time)/60:.1f} minutes.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
