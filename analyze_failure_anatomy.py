"""Build trajectory-linked failure anatomy for the 20-model paper artifact.

Run from a reconstructed artifact (``reconstruct_artifact.py``) or directly
from the chunked tree: logical ``*.jsonl`` files are read when present and
their ``*.parts/`` directories otherwise.
"""

from __future__ import annotations

import collections
import hashlib
import itertools
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT_JSON = ROOT / "paper/FAILURE_ANATOMY.json"
OUT_MD = ROOT / "paper/FAILURE_ANATOMY.md"

# Paper leaderboard order. Each entry: (hybrid score file, subject result file).
MODELS = {
    "GPT-6 Astra": ("runs/hybrid_gpt6astra/hybrid_scores.jsonl", "runs/subject_gpt6astra/results.jsonl"),
    "Grok 4.6": ("runs/hybrid_grok46/hybrid_scores.jsonl", "runs/subject_grok46/results.jsonl"),
    "Claude Opus 5.5": ("runs/hybrid_opus55/hybrid_scores.jsonl", "runs/subject_opus55/results.jsonl"),
    "Qwen 3.8 Max": ("runs/hybrid_qwen38max/hybrid_scores.jsonl", "runs/subject_qwen38max/results.jsonl"),
    "GPT-5.5": ("runs/hybrid_gpt55/hybrid_scores.jsonl", "runs/subject_gpt55/results.jsonl"),
    "GPT-6 Sol": ("runs/hybrid_gpt6sol/hybrid_scores.jsonl", "runs/subject_gpt6sol/results.jsonl"),
    "GPT-5.6 Sol": ("runs/hybrid_sol/hybrid_scores.jsonl", "runs/subject_sol/results.jsonl"),
    "Qwen 3.8 Flash Next": (
        "runs/hybrid_qwen38flashnext/hybrid_scores.jsonl",
        "runs/subject_qwen38flashnext/results.jsonl",
    ),
    "Gemini 3.7 Flash": (
        "runs/hybrid_gemini37flash/hybrid_scores.jsonl",
        "runs/subject_gemini37flash/results.jsonl",
    ),
    "Claude Fable 5.1": ("runs/hybrid_fable51/hybrid_scores.jsonl", "runs/subject_fable51/results.jsonl"),
    "Claude Opus 4.8": ("runs/hybrid_opus48/hybrid_scores.jsonl", "runs/subject_opus48/results.jsonl"),
    "GPT-6 Luna": ("runs/hybrid_gpt6luna/hybrid_scores.jsonl", "runs/subject_gpt6luna/results.jsonl"),
    "Claude Opus 5": ("runs/hybrid_opus5/hybrid_scores.jsonl", "runs/subject_opus5/results.jsonl"),
    "GLM 5.3": ("runs/hybrid_glm53/hybrid_scores.jsonl", "runs/subject_glm53/results.jsonl"),
    "Qwen-AgentWorld-35B-A3B": (
        "runs/external_hybrid_final/qwen-agentworld/hybrid_scores.jsonl",
        "runs/external_qwen_agentworld/results.jsonl",
    ),
    "Kimi K3": ("runs/hybrid_kimi_k3/hybrid_scores.jsonl", "runs/subject_kimi_k3/results.jsonl"),
    "Inkling": ("runs/hybrid_inkling/hybrid_scores.jsonl", "runs/subject_inkling/results.jsonl"),
    "Claude Fable 5": ("runs/hybrid_fable5/hybrid_scores.jsonl", "runs/subject_fable5/results.jsonl"),
    "DWM": ("runs/external_hybrid_final/dwm/hybrid_scores.jsonl", "runs/external_dwm/results.jsonl"),
    "Laguna S2.1": ("runs/hybrid_laguna/hybrid_scores.jsonl", "runs/subject_laguna/results.jsonl"),
}
SPECIALIZED = ("Qwen-AgentWorld-35B-A3B", "DWM")
GENERAL = tuple(label for label in MODELS if label not in SPECIALIZED)
DOMAINS = ("game", "enterprise", "code", "math_and_science", "dialogue")
DOMAIN_NAMES = {
    "game": "Games", "enterprise": "Enterprise", "code": "Code",
    "math_and_science": "Math/Sci.", "dialogue": "Dialogue",
}
CATEGORIES = (
    "wrong_value_only",
    "wrong_value_plus_structure",
    "schema_substitution",
    "omission_only",
    "invention_only",
    "semantic_or_error_surface",
)
CATEGORY_NAMES = {
    "wrong_value_only": "Wrong value only",
    "wrong_value_plus_structure": "Wrong value + missing/invented structure",
    "schema_substitution": "Schema substitution",
    "omission_only": "Omission only",
    "invention_only": "Invention only",
    "semantic_or_error_surface": "Semantic or error surface",
}
WRONG = ("wrong_value_only", "wrong_value_plus_structure")
STRUCTURAL = ("schema_substitution", "omission_only", "invention_only")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def logical_files(path: Path) -> list[Path]:
    """A logical JSONL file, or its row-boundary parts in the chunked tree."""
    if path.is_file():
        return [path]
    parts = path.with_suffix(".parts")
    if parts.is_dir():
        return sorted(parts.glob("*.jsonl"))
    raise FileNotFoundError(path)


def read_rows(path: Path) -> list[dict]:
    return [row for part in logical_files(path) for row in read_jsonl(part)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for part in logical_files(path):
        digest.update(part.read_bytes())
    return digest.hexdigest()


def pct(count: int, total: int) -> float:
    """Percentage rounded half-up to two decimals (the paper's convention)."""
    if not total:
        return 0.0
    value = (Decimal(count) * 100 / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(value)


def answered(row: dict) -> bool:
    return row["served_state"] == "served"


def outcome(row: dict) -> str:
    """pass, fail (usable response that failed), or no_response."""
    if row["semantic_outcome"] == "pass":
        return "pass"
    return "fail" if answered(row) else "no_response"


def anatomy(row: dict) -> str:
    detail = row["deterministic"]
    wrong = bool(detail.get("contradictory_claims"))
    missing = bool(detail.get("missing_claims"))
    extra = bool(detail.get("extra_claims"))
    if wrong and not missing and not extra:
        return "wrong_value_only"
    if not wrong and missing and extra:
        return "schema_substitution"
    if wrong and (missing or extra):
        return "wrong_value_plus_structure"
    if missing and not extra:
        return "omission_only"
    if extra and not missing:
        return "invention_only"
    return "semantic_or_error_surface"


def horizon(value) -> str:
    if value is None:
        return "none"
    value = int(value)
    if value <= 4:
        return "<=4"
    if value <= 16:
        return "5-16"
    if value <= 40:
        return "17-40"
    if value <= 80:
        return "41-80"
    return ">80"


def horizon_40(value) -> str:
    if value is None:
        return "none"
    return "<=40" if int(value) <= 40 else ">40"


def distribution(counter: collections.Counter, total: int | None = None) -> dict:
    total = sum(counter.values()) if total is None else total
    return {key: {"n": value, "pct": pct(value, total)} for key, value in counter.most_common()}


def failure_block(rows: list[dict]) -> dict:
    """Anatomy of all non-pass decisions; category shares over answered failures."""
    failed = [row for row in rows if row["semantic_outcome"] != "pass"]
    answered_failures = [row for row in failed if answered(row)]
    counts = collections.Counter(anatomy(row) for row in answered_failures)
    n_answered = len(answered_failures)
    return {
        "failed_decisions": len(failed),
        "no_usable_response": len(failed) - n_answered,
        "no_usable_response_pct_of_failures": pct(len(failed) - n_answered, len(failed)),
        "answered_failures": n_answered,
        "categories": {key: {"n": counts[key], "pct": pct(counts[key], n_answered)} for key in CATEGORIES},
        "any_wrong_value": {"n": sum(counts[k] for k in WRONG), "pct": pct(sum(counts[k] for k in WRONG), n_answered)},
        "purely_structural": {
            "n": sum(counts[k] for k in STRUCTURAL), "pct": pct(sum(counts[k] for k in STRUCTURAL), n_answered)
        },
    }


def outcome_table(buckets: dict[str, collections.Counter]) -> dict:
    return {
        key: {
            "n": sum(counts.values()),
            "pass": counts["pass"],
            "fail": counts["fail"],
            "no_response": counts["no_response"],
            "pass_pct": pct(counts["pass"], sum(counts.values())),
            "fail_pct": pct(counts["fail"] + counts["no_response"], sum(counts.values())),
            "no_response_pct": pct(counts["no_response"], sum(counts.values())),
        }
        for key, counts in sorted(buckets.items())
    }


def clip(text: str, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build() -> dict:
    items = {row["example_id"]: row for row in read_rows(ROOT / "data/eval.jsonl")}
    scores, results = {}, {}
    for label, (score_path, result_path) in MODELS.items():
        scores[label] = {row["item_id"]: row for row in read_rows(ROOT / score_path)}
        results[label] = {row["item_id"]: row for row in read_rows(ROOT / result_path)}
        if set(scores[label]) != set(items):
            raise RuntimeError(f"{label}: score rows do not cover the released items")

    all_rows = [row for label in MODELS for row in scores[label].values()]
    general_rows = [row for label in GENERAL for row in scores[label].values()]
    population = {
        "all": failure_block(all_rows),
        "by_domain": {
            domain: failure_block([row for row in all_rows if row["domain"] == domain])
            for domain in DOMAINS
        },
    }
    general = failure_block(general_rows)
    by_model = {label: failure_block(list(scores[label].values())) for label in MODELS}
    answered_failures = [
        (label, item_id, row)
        for label in MODELS
        for item_id, row in scores[label].items()
        if row["semantic_outcome"] != "pass" and answered(row)
    ]
    resolution = distribution(collections.Counter(row["resolution_rule"] for _, _, row in answered_failures))
    modes = distribution(collections.Counter(row["deterministic"].get("mode", "") for _, _, row in answered_failures))

    decision_axes = {}
    for axis, key_fn in (
        ("radius", lambda item: item["metadata"].get("radius_level") or "none"),
        ("horizon", lambda item: horizon(item["metadata"].get("h_reachback"))),
        ("horizon_40", lambda item: horizon_40(item["metadata"].get("h_reachback"))),
    ):
        buckets: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for label in MODELS:
            for item_id, row in scores[label].items():
                buckets[key_fn(items[item_id])][outcome(row)] += 1
        decision_axes[axis] = outcome_table(buckets)

    decision_by_domain: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    decision_by_skill: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    decision_by_primary_skill: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    skill_operators: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for item in items.values():
        for skill in item["metadata"]["sub_evals"]:
            skill_operators[skill][item["metadata"]["operator"]] += 1
    for label in MODELS:
        for item_id, row in scores[label].items():
            result = outcome(row)
            decision_by_domain[row["domain"]][result] += 1
            for skill in row["sub_evals"]:
                decision_by_skill[skill][result] += 1
            decision_by_primary_skill[items[item_id]["metadata"]["primary_sub_eval"]][result] += 1

    item_difficulty = []
    for item_id, item in items.items():
        counts = collections.Counter(outcome(scores[label][item_id]) for label in MODELS)
        item_difficulty.append({
            "item_id": item_id,
            "domain": item["metadata"]["domain"],
            "operator": item["metadata"]["operator"],
            "sub_evals": item["metadata"]["sub_evals"],
            "h_reachback": item["metadata"].get("h_reachback"),
            "radius_level": item["metadata"].get("radius_level"),
            "pass": counts["pass"],
            "fail": counts["fail"] + counts["no_response"],
            "no_response": counts["no_response"],
        })
    n_models = len(MODELS)
    pass_histogram = collections.Counter(row["pass"] for row in item_difficulty)
    hardest = sorted(item_difficulty, key=lambda row: (row["pass"], -row["no_response"], row["item_id"]))[:20]
    universal_fail_operators = collections.Counter(
        row["operator"] for row in item_difficulty if row["pass"] == 0
    )
    solved_by_any = sum(row["pass"] > 0 for row in item_difficulty)
    leader = next(iter(MODELS))
    solved_by_others = sum(
        any(scores[label][item_id]["semantic_outcome"] == "pass" for label in MODELS if label != leader)
        for item_id in items
    )

    pairwise = {}
    for left, right in itertools.combinations(MODELS, 2):
        counts = collections.Counter()
        for item_id in items:
            a = scores[left][item_id]["semantic_outcome"] == "pass"
            b = scores[right][item_id]["semantic_outcome"] == "pass"
            counts["both_pass" if a and b else "left_only" if a else "right_only" if b else "both_fail"] += 1
        pairwise[f"{left} vs {right}"] = dict(sorted(counts.items()))

    leaf_presence = collections.Counter()
    for _, _, row in answered_failures:
        leaves = set()
        for field in ("contradictory_claims", "missing_claims", "extra_claims"):
            for path in row["deterministic"].get(field, []):
                leaves.add(re.sub(r"\[\d+\]", "[]", path).split(".")[-1])
        leaf_presence.update(leaves)

    preferences = [
        ("wrong_value_only", "GPT-5.6 Sol", None),
        ("omission_only", "Grok 4.6", None),
        ("schema_substitution", "Gemini 3.7 Flash", None),
        ("schema_substitution", "GPT-6 Astra", None),
        ("wrong_value_plus_structure", "Claude Opus 4.8", None),
        ("semantic_or_error_surface", "Qwen 3.8 Max", "error_missing"),
        ("semantic_or_error_surface", "Grok 4.6", "error_referent"),
        ("semantic_or_error_surface", "Claude Opus 4.8", "mismatch"),
    ]
    evidence = []
    for category, preferred_model, mode in preferences:
        candidates = []
        for label, item_id, row in answered_failures:
            if label != preferred_model or anatomy(row) != category:
                continue
            if mode and row["deterministic"].get("mode") != mode:
                continue
            raw = results[label].get(item_id)
            if raw is None:
                continue
            item = items[item_id]
            prompt_chars = sum(len(message["content"]) for message in item["messages"])
            if len(str(raw.get("gold", ""))) > 3500 or len(str(raw.get("prediction", ""))) > 3500:
                continue
            candidates.append((prompt_chars, item_id, row, raw, item))
        if not candidates:
            continue
        prompt_chars, item_id, row, raw, item = min(candidates, key=lambda entry: (entry[0], entry[1]))
        detail = row["deterministic"]
        evidence.append({
            "category": category,
            "model": preferred_model,
            "item_id": item_id,
            "domain": row["domain"],
            "operator": row["operator"],
            "sub_evals": row["sub_evals"],
            "radius": item["metadata"].get("radius_level"),
            "h_reachback": item["metadata"].get("h_reachback"),
            "prompt_chars": prompt_chars,
            "resolution_rule": row["resolution_rule"],
            "deterministic_mode": detail.get("mode", ""),
            "contradictory_claims": detail.get("contradictory_claims", [])[:12],
            "missing_claims": detail.get("missing_claims", [])[:12],
            "extra_claims": detail.get("extra_claims", [])[:12],
            "final_action": clip(item["messages"][-1]["content"], 900),
            "gold": clip(item["target"], 900),
            "prediction": clip(raw.get("prediction", ""), 900),
        })

    return {
        "schema": "wm-failure-anatomy/2",
        "scope": {
            "items": len(items),
            "models": list(MODELS),
            "general_models": list(GENERAL),
            "specialized_world_models": list(SPECIALIZED),
            "decisions": len(all_rows),
            "passes": sum(row["semantic_outcome"] == "pass" for row in all_rows),
            "failed_decisions": population["all"]["failed_decisions"],
            "no_usable_response": population["all"]["no_usable_response"],
            "answered_failures": population["all"]["answered_failures"],
        },
        "population_failure_anatomy": population,
        "general_model_failure_anatomy": general,
        "failure_anatomy_by_model": by_model,
        "answered_failure_resolution_evidence": resolution,
        "answered_failure_deterministic_modes": modes,
        "decision_outcomes_by_axis": decision_axes,
        "decision_outcomes_by_domain": outcome_table(decision_by_domain),
        "decision_outcomes_by_skill_any_label": outcome_table(decision_by_skill),
        "decision_outcomes_by_primary_skill": outcome_table(decision_by_primary_skill),
        "skill_operator_concentration": {
            skill: {
                "n_items": sum(counts.values()),
                "unique_operators": len(counts),
                "top_operator": counts.most_common(1)[0][0],
                "top_operator_n": counts.most_common(1)[0][1],
                "top_operator_pct": pct(counts.most_common(1)[0][1], sum(counts.values())),
            }
            for skill, counts in sorted(skill_operators.items())
        },
        "item_difficulty": {
            "models": n_models,
            "pass_count_histogram": {str(key): value for key, value in sorted(pass_histogram.items())},
            "solved_by_no_model": pass_histogram[0],
            "solved_by_all_models": pass_histogram[n_models],
            "solved_by_at_least_one_model": solved_by_any,
            "oracle_best_model_per_item_pct": pct(solved_by_any, len(items)),
            "leader": leader,
            "leader_passes": sum(scores[leader][i]["semantic_outcome"] == "pass" for i in items),
            "items_solved_by_any_other_model": solved_by_others,
            "hardest_items": hardest,
            "universal_fail_operators": [
                {"operator": operator, "n": n, "pct": pct(n, sum(universal_fail_operators.values()))}
                for operator, n in universal_fail_operators.most_common(20)
            ],
        },
        "pairwise_pass_complementarity": pairwise,
        "top_changed_or_missing_leaf_names_by_row_presence": [
            {"leaf": leaf, "failure_rows": count} for leaf, count in leaf_presence.most_common(30)
        ],
        "evidence_cards": evidence,
        "interpretation_notes": [
            "Counts are model-item decisions, not unique trajectories.",
            "A decision without a usable response (provider refusal, empty or errored completion) is a failure and stays in every denominator; it forms its own bucket and is excluded from the category shares.",
            "Anatomy categories are mutually exclusive diagnostics derived from deterministic claim paths; category shares are over answered failures.",
            "semantic_or_error_surface includes LLM-adjudicated natural-language cases and explicit error-surface mismatches without structured paths.",
            "Skill slices are any-label and overlap; primary-skill slices partition the items.",
            "Field-frequency counts measure presence per failed row, not the number of wrong array cells.",
            "Axis associations are descriptive; item families are not held constant.",
            "Output evidence supports behavioral descriptions, not claims about hidden model reasoning.",
            "Percentages are rounded half-up to two decimals.",
        ],
        "source_hashes": {
            "eval_data": sha256(ROOT / "data/eval.jsonl"),
            **{f"score:{label}": sha256(ROOT / score_path) for label, (score_path, _) in MODELS.items()},
        },
    }


def markdown(report: dict) -> str:
    population = report["population_failure_anatomy"]
    total = population["all"]
    scope = report["scope"]
    difficulty = report["item_difficulty"]
    grok_sol = report["pairwise_pass_complementarity"]["Grok 4.6 vs GPT-5.6 Sol"]
    lines = [
        "# Failure anatomy across the 20-model sweep",
        "",
        "This report moves from leaderboard totals to observable failure mechanisms. It covers all 20 evaluated models (18 general-purpose LLMs and two specialized text world models) on the same 1,632 items. Every example is tied to a released item, raw prediction, executed gold, and deterministic or LLM resolution rule.",
        "",
        "## Main findings",
        "",
        f"- The sweep contains **{scope['decisions']:,} model-item decisions** and **{scope['passes']:,} passes** ({pct(scope['passes'], scope['decisions']):.2f}%).",
        f"- Of the **{total['failed_decisions']:,} failed decisions**, **{total['no_usable_response']:,}** have no usable response (provider refusals plus empty or errored completions) and **{total['answered_failures']:,}** are answered failures.",
        f"- A wrong concrete value appears in **{total['any_wrong_value']['pct']:.2f}%** of answered failures: {total['categories']['wrong_value_only']['pct']:.2f}% wrong value only and {total['categories']['wrong_value_plus_structure']['pct']:.2f}% wrong values combined with missing or invented structure.",
        f"- **{total['purely_structural']['pct']:.2f}%** of answered failures are purely structural (schema substitution, omission, or invention without a shared wrong value); **{total['categories']['semantic_or_error_surface']['pct']:.2f}%** have no structured claim path.",
        f"- Failure shape depends on the domain: {population['by_domain']['game']['categories']['semantic_or_error_surface']['pct']:.2f}% of answered Games failures are semantic or error-surface failures, while {population['by_domain']['math_and_science']['categories']['wrong_value_plus_structure']['pct']:.2f}% of answered Math/Science failures combine a wrong value with missing or invented structure.",
        f"- Aggregate rank is not dominance: Grok 4.6 passes {grok_sol.get('left_only', 0)} items that GPT-5.6 Sol fails, while Sol passes {grok_sol.get('right_only', 0)} that Grok fails.",
        f"- {difficulty['solved_by_at_least_one_model']:,} items ({difficulty['oracle_best_model_per_item_pct']:.2f}%) are solved by at least one model, {difficulty['solved_by_no_model']} by none, and {difficulty['solved_by_all_models']} by all {difficulty['models']}. {difficulty['leader']} alone solves {difficulty['leader_passes']} items; the other {difficulty['models'] - 1} models together solve {difficulty['items_solved_by_any_other_model']}.",
        "",
        "## Failure anatomy over the 20 models",
        "",
        "Counts in the first block; category shares (%) are over answered failures.",
        "",
        "| Category | All | " + " | ".join(DOMAIN_NAMES[d] for d in DOMAINS) + " |",
        "|---|" + "---:|" * (len(DOMAINS) + 1),
    ]
    blocks = [total] + [population["by_domain"][d] for d in DOMAINS]
    for key, name in (("failed_decisions", "Failed decisions"), ("no_usable_response", "No usable response"),
                      ("answered_failures", "Answered failures")):
        lines.append(f"| {name} | " + " | ".join(f"{block[key]:,}" for block in blocks) + " |")
    for key in CATEGORIES:
        lines.append(f"| {CATEGORY_NAMES[key]} | " + " | ".join(f"{block['categories'][key]['pct']:.2f}" for block in blocks) + " |")
    lines.append("| *Any wrong value* | " + " | ".join(f"{block['any_wrong_value']['pct']:.2f}" for block in blocks) + " |")
    lines.append("| *Purely structural* | " + " | ".join(f"{block['purely_structural']['pct']:.2f}" for block in blocks) + " |")

    general = report["general_model_failure_anatomy"]
    lines += [
        "",
        f"Restricted to the 18 general-purpose LLMs: {general['failed_decisions']:,} failed decisions, {general['no_usable_response']:,} without a usable response, {general['answered_failures']:,} answered failures, {general['any_wrong_value']['pct']:.2f}% of them with a wrong value.",
        "",
        "## Model-specific profiles",
        "",
        "The no-usable-response share is over each model's failed decisions; category shares are over its answered failures. They describe failure composition, not accuracy.",
        "",
        "| Model | Failed | No usable response | Wrong value only | Wrong + structure | Schema substitution | Omission only | Invention only | Semantic/error |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, block in report["failure_anatomy_by_model"].items():
        cats = block["categories"]
        lines.append(
            f"| {label} | {block['failed_decisions']:,} | {block['no_usable_response_pct_of_failures']:.2f}% | "
            + " | ".join(f"{cats[key]['pct']:.2f}%" for key in CATEGORIES) + " |"
        )

    lines += [
        "",
        "## Skill-level difficulty (any-label, 20 models pooled)",
        "",
        "Rows have multiple skill labels, so these are overlapping diagnostic slices, not additive categories. Decisions without a usable response count as failures.",
        "",
        "| Skill | Model-item decisions | Pass | Fail | of which no response | Operators | Top-operator share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for skill, row in sorted(
        report["decision_outcomes_by_skill_any_label"].items(), key=lambda pair: (pair[1]["pass_pct"], pair[0])
    ):
        concentration = report["skill_operator_concentration"][skill]
        lines.append(
            f"| `{skill}` | {row['n']:,} | {row['pass_pct']:.2f}% | {row['fail_pct']:.2f}% | "
            f"{row['no_response_pct']:.2f}% | {concentration['unique_operators']} | {concentration['top_operator_pct']:.2f}% |"
        )
    lines += [
        "",
        "## Primary-skill difficulty (20 models pooled)",
        "",
        "| Primary skill | Model-item decisions | Pass | Fail |",
        "|---|---:|---:|---:|",
    ]
    for skill, row in sorted(
        report["decision_outcomes_by_primary_skill"].items(), key=lambda pair: (pair[1]["pass_pct"], pair[0])
    ):
        lines.append(f"| `{skill}` | {row['n']:,} | {row['pass_pct']:.2f}% | {row['fail_pct']:.2f}% |")

    lines += [
        "",
        "## Difficulty concentration across items",
        "",
        f"- **{difficulty['solved_by_no_model']}** items are failed by all {difficulty['models']} models; **{difficulty['solved_by_all_models']}** are passed by all {difficulty['models']}.",
        "- A high shared-failure count identifies a hard item, not a single underlying cognitive cause; the trajectory evidence still determines whether it is state recall, computation, schema, or error semantics.",
        f"- The largest operator among universal failures is `{difficulty['universal_fail_operators'][0]['operator']}` ({difficulty['universal_fail_operators'][0]['n']} items, {difficulty['universal_fail_operators'][0]['pct']:.2f}%). This concentration is reported so repeated constructions are not mistaken for independent failure mechanisms.",
        "",
        f"| Item | Domain | Operator | Passed / {difficulty['models']} | No response | Skills |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in difficulty["hardest_items"][:10]:
        lines.append(
            f"| `{row['item_id']}` | {row['domain']} | `{row['operator']}` | {row['pass']} | "
            f"{row['no_response']} | {', '.join(row['sub_evals'][:4])} |"
        )

    lines += [
        "",
        "## Controlled-axis associations (20 models pooled)",
        "",
        "These aggregate slices are not matched-family causal ablations: operator and domain composition also changes across buckets.",
        "",
        "| Axis | Bucket | Decisions | Pass | Fail | of which no response |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for axis, buckets in report["decision_outcomes_by_axis"].items():
        for bucket, row in buckets.items():
            lines.append(
                f"| {axis} | `{bucket}` | {row['n']:,} | {row['pass_pct']:.2f}% | {row['fail_pct']:.2f}% | {row['no_response_pct']:.2f}% |"
            )

    lines += ["", "## Trajectory-backed examples", ""]
    for card in report["evidence_cards"]:
        lines += [
            f"### `{card['category']}` — {card['model']}",
            "",
            f"- Item: `{card['item_id']}`; domain/operator: `{card['domain']}` / `{card['operator']}`; radius/reach-back: {card['radius']} / {card['h_reachback']}",
            f"- Resolution: `{card['resolution_rule']}` / `{card['deterministic_mode']}`",
            f"- Contradictory paths: {', '.join(f'`{x}`' for x in card['contradictory_claims']) or 'none'}",
            f"- Missing paths: {', '.join(f'`{x}`' for x in card['missing_claims']) or 'none'}",
            f"- Extra paths: {', '.join(f'`{x}`' for x in card['extra_claims']) or 'none'}",
            f"- Final action: `{card['final_action']}`",
            f"- Executed gold: `{card['gold']}`",
            f"- Model prediction: `{card['prediction']}`",
            "",
        ]

    lines += [
        "## Reproduce",
        "",
        "```bash",
        "python reconstruct_artifact.py --artifact-dir . --out-dir reconstructed",
        "(cd reconstructed && python analyze_failure_anatomy.py)",
        "```",
        "",
        "The JSON companion contains complete counts, per-model and per-domain blocks, pairwise complementarity for all 190 model pairs, evidence cards, source hashes, and interpretation notes.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = build()
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["scope"], indent=2))


if __name__ == "__main__":
    main()
