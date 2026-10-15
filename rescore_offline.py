#!/usr/bin/env python3
"""Rescore the released runs without querying any model or judge.

For every model and item the script
1. counts a row without a usable subject response as a failure;
2. re-grades each served prediction against the released target with the
   shipped ``deterministic_grader.py`` (certified equivalence -> pass,
   concrete contradiction -> fail);
3. otherwise applies the stored LLM verdict: the primary judge
   (GPT-5.6 Terra), or the Sol fallback when the fused record names it,
   looked up in the released ``judgments`` files, and checks that the judge
   record carrying that verdict has the ``prompt_sha256`` of the judge prompt
   that ``harness.judge_messages`` renders from the released item and the
   released prediction;
and compares the recomputed outcome with the released fused decision.

The git-status adapter, used on five shell/code items (79 decisions in total),
is not part of the shipped grader; its stored decision is reused and counted
separately.
Works on the chunked tree and on a reconstructed tree.
"""

from __future__ import annotations

import argparse
import collections
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import harness
from deterministic_grader import grade_detail, grader_fingerprint

# Paper order: label, fused scores, subject results.
MODELS = (
    ("GPT-6 Astra", "runs/hybrid_gpt6astra/hybrid_scores", "runs/subject_gpt6astra/results"),
    ("Grok 4.6", "runs/hybrid_grok46/hybrid_scores", "runs/subject_grok46/results"),
    ("Claude Opus 5.5", "runs/hybrid_opus55/hybrid_scores", "runs/subject_opus55/results"),
    ("Qwen 3.8 Max", "runs/hybrid_qwen38max/hybrid_scores", "runs/subject_qwen38max/results"),
    ("GPT-5.5", "runs/hybrid_gpt55/hybrid_scores", "runs/subject_gpt55/results"),
    ("GPT-6 Sol", "runs/hybrid_gpt6sol/hybrid_scores", "runs/subject_gpt6sol/results"),
    ("GPT-5.6 Sol", "runs/hybrid_sol/hybrid_scores", "runs/subject_sol/results"),
    ("Qwen 3.8 Flash Next", "runs/hybrid_qwen38flashnext/hybrid_scores", "runs/subject_qwen38flashnext/results"),
    ("Gemini 3.7 Flash", "runs/hybrid_gemini37flash/hybrid_scores", "runs/subject_gemini37flash/results"),
    ("Claude Fable 5.1", "runs/hybrid_fable51/hybrid_scores", "runs/subject_fable51/results"),
    ("Claude Opus 4.8", "runs/hybrid_opus48/hybrid_scores", "runs/subject_opus48/results"),
    ("GPT-6 Luna", "runs/hybrid_gpt6luna/hybrid_scores", "runs/subject_gpt6luna/results"),
    ("Claude Opus 5", "runs/hybrid_opus5/hybrid_scores", "runs/subject_opus5/results"),
    ("GLM 5.3", "runs/hybrid_glm53/hybrid_scores", "runs/subject_glm53/results"),
    ("Qwen-AgentWorld-35B-A3B", "runs/external_hybrid_final/qwen-agentworld/hybrid_scores",
     "runs/external_qwen_agentworld/results"),
    ("Kimi K3", "runs/hybrid_kimi_k3/hybrid_scores", "runs/subject_kimi_k3/results"),
    ("Inkling", "runs/hybrid_inkling/hybrid_scores", "runs/subject_inkling/results"),
    ("Claude Fable 5", "runs/hybrid_fable5/hybrid_scores", "runs/subject_fable5/results"),
    ("DWM", "runs/external_hybrid_final/dwm/hybrid_scores", "runs/external_dwm/results"),
    ("Laguna S2.1", "runs/hybrid_laguna/hybrid_scores", "runs/subject_laguna/results"),
)


def logical_rows(root: Path, stem: str) -> list[dict]:
    """Rows of ``<stem>.jsonl``, or of its ``<stem>.parts/`` chunks."""
    single = root / f"{stem}.jsonl"
    files = [single] if single.is_file() else sorted((root / f"{stem}.parts").glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(single)
    return [
        json.loads(line)
        for path in files
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_judge_records(root: Path) -> tuple[dict, dict]:
    """Decisive verdicts, and (verdict, prompt_sha256) pairs, per judge key."""
    verdicts: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    prompts: dict[tuple[str, str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    paths = sorted(root.glob("runs/**/judgments.jsonl")) + sorted(root.glob("runs/**/judgments.parts/*.jsonl"))
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("effective_verdict") in {"pass", "fail"}:
                key = (row.get("subject_model_key"), row.get("item_id"), row.get("judge_model"))
                verdicts[key].add(row["effective_verdict"])
                prompts[key].add((row["effective_verdict"], row.get("prompt_sha256")))
    return verdicts, prompts


def load_verdicts(root: Path) -> dict[tuple[str, str, str], set[str]]:
    return load_judge_records(root)[0]


def judge_item(item: dict, contracts: dict[str, dict]) -> dict:
    """A released item in the form that ``harness.judge_messages`` renders."""
    scoring = item["metadata"].get("scoring", {})
    row = {"messages": item["messages"], "executed_gold": item["target"], "scoring_contract": scoring}
    if not scoring and item["example_id"] in contracts:
        row["judge_scoring_contract"] = contracts[item["example_id"]]
    return row


def pct(passes: int, total: int) -> str:
    return str((Decimal(passes) * 100 / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def rescore(root: Path) -> list[dict]:
    items = {row["example_id"]: row for row in logical_rows(root, "data/eval")}
    contracts_path = root / "data" / harness.JUDGE_CONTRACTS_FILE
    contracts = harness.load_judge_contracts(contracts_path) if contracts_path.is_file() else {}
    verdicts, prompts = load_judge_records(root)
    report = []
    for label, score_stem, result_stem in MODELS:
        scores = logical_rows(root, score_stem)
        results = {row["item_id"]: row for row in logical_rows(root, result_stem)}
        counts = collections.Counter()
        passes = 0
        for score in scores:
            item_id = score["item_id"]
            if score["served_state"] != "served":
                outcome, route = "fail", "no_usable_response"
            elif score.get("deterministic_adapter"):
                outcome, route = score["semantic_outcome"], "stored_adapter_decision"
            else:
                item = items[item_id]
                scoring = item["metadata"].get("scoring", {})
                prediction = str(results[item_id].get("prediction", ""))
                grade = grade_detail(
                    prediction, str(item["target"]),
                    order_sensitive=bool(scoring.get("order_sensitive", True)),
                    required_error_level=scoring.get("required_error_level", "referent"),
                )
                if grade.correct:
                    outcome, route = "pass", "deterministic"
                elif not grade.adjudication_required:
                    outcome, route = "fail", "deterministic"
                else:
                    judge = (
                        score.get("secondary_judge_model")
                        if score["resolution_rule"] == "secondary_semantic_adjudication"
                        else score.get("primary_judge_model")
                    )
                    key = (score["model_key"], item_id, judge)
                    found = verdicts.get(key, set())
                    if len(found) == 1:
                        outcome, route = next(iter(found)), "stored_judge_verdict"
                        prompt = harness.judge_prompt_sha256(
                            harness.judge_messages(judge_item(item, contracts), prediction)
                        )
                        bound = (outcome, prompt) in prompts.get(key, set())
                        counts["judge_prompt_bound" if bound else "JUDGE_PROMPT_UNBOUND"] += 1
                    else:
                        outcome, route = "unresolved", f"judge_verdicts:{sorted(found)}"
            stored = "pass" if score["semantic_outcome"] == "pass" else "fail"
            counts[route] += 1
            counts["match" if outcome == stored else "MISMATCH"] += 1
            passes += outcome == "pass"
        report.append({
            "model": label, "pass": passes, "total": len(scores),
            "task_success_pct": pct(passes, len(scores)), "routes": dict(counts),
        })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--json", action="store_true", help="print machine-readable rows")
    args = parser.parse_args()
    report = rescore(args.root)
    if args.json:
        print(json.dumps({"grader_fingerprint": grader_fingerprint(), "models": report}, indent=2))
    else:
        print(f"grader {grader_fingerprint()}")
        print(f"{'model':<26}{'pass':>6}{'total':>7}{'task success':>14}{'mismatches':>12}")
        for row in report:
            print(f"{row['model']:<26}{row['pass']:>6}{row['total']:>7}{row['task_success_pct']:>13}%"
                  f"{row['routes'].get('MISMATCH', 0):>12}")
        passes = sum(row["pass"] for row in report)
        total = sum(row["total"] for row in report)
        print(f"{'All 20 (pooled)':<26}{passes:>6}{total:>7}{pct(passes, total):>13}%")
        applied = sum(row["routes"].get("stored_judge_verdict", 0) for row in report)
        bound = sum(row["routes"].get("judge_prompt_bound", 0) for row in report)
        print(f"judge verdicts bound to the released item and prediction by prompt_sha256: {bound} / {applied}")
    failed = any(
        row["routes"].get("MISMATCH") or row["routes"].get("JUDGE_PROMPT_UNBOUND") for row in report
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
