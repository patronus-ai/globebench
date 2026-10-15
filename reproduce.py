#!/usr/bin/env python3
"""Re-run the paper's 16 OpenRouter-served models on a local copy of the items.

Pass --expected-sha256 to pin the item file. This driver queries the subject
and judge models again and needs OPENROUTER_API_KEY. To rescore the released
runs without querying any model, use rescore_offline.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import harness

# General-purpose models reachable through OpenRouter (OpenRouter model ids).
# GPT-5.6 Sol and Claude Opus 4.8 were served through their first-party APIs
# in the paper (see FIRST_PARTY_IN_PAPER); this driver sends every model
# through OpenRouter.
MODELS = {
    "anthropic/claude-opus-4.8": "Claude Opus 4.8",
    "openai/gpt-5.6-sol": "GPT-5.6 Sol",
    "openai/gpt-5.5": "GPT-5.5",
    "google/gemini-3.7-flash": "Gemini 3.7 Flash",
    "poolside/laguna-s-2.1": "Laguna S2.1",
    "moonshotai/kimi-k3": "Kimi K3",
    "thinkingmachines/inkling": "Inkling",
    "z-ai/glm-5.3": "GLM 5.3",
    "x-ai/grok-4.6": "Grok 4.6",
    "qwen/qwen3.8-max": "Qwen 3.8 Max",
    "openai/gpt-6-sol": "GPT-6 Sol",
    "openai/gpt-6-luna": "GPT-6 Luna",
    "anthropic/claude-opus-5.5": "Claude Opus 5.5",
    "anthropic/claude-opus-5": "Claude Opus 5",
    "anthropic/claude-fable-5.1": "Claude Fable 5.1",
    "anthropic/claude-fable-5": "Claude Fable 5",
}
# Paper models that were not served through OpenRouter. Run them with
# harness.py directly and the listed route (see README).
OTHER_ROUTES = {
    "gpt-6-astra": "GPT-6 Astra: OpenAI API (--api-base https://api.openai.com/v1 --api-key-env OPENAI_API_KEY)",
    "qwen3.8-flash-next": "Qwen 3.8 Flash Next: OpenAI-compatible endpoint (--api-base)",
    "Qwen/Qwen-AgentWorld-35B-A3B": "Qwen-AgentWorld-35B-A3B: OpenAI-compatible endpoint (--api-base)",
    "dwm": "DWM: OpenAI-compatible endpoint (--api-base)",
}
FIRST_PARTY_IN_PAPER = {
    "openai/gpt-5.6-sol": "GPT-5.6 Sol: OpenAI API, reasoning_effort high",
    "anthropic/claude-opus-4.8": "Claude Opus 4.8: Anthropic API, adaptive thinking, effort high",
}
PRIMARY_JUDGE = "openai/gpt-5.6-terra"
SECONDARY_JUDGE = "openai/gpt-5.6-sol"
# Output budgets of the paper's primary requests (recorded in each subject
# row's params.max_tokens). A few rows used other budgets, recorded in the
# rows. Arguments after -- override these.
DEFAULT_SUBJECT_BUDGET = 65536
SUBJECT_BUDGETS = {
    "openai/gpt-5.6-sol": 32000,
    "anthropic/claude-opus-4.8": 32000,
}
JUDGE_BUDGET = 16384


def budget_arguments(model: str) -> tuple[str, ...]:
    return (
        "--subject-max-tokens", str(SUBJECT_BUDGETS.get(model, DEFAULT_SUBJECT_BUDGET)),
        "--judge-max-tokens", str(JUDGE_BUDGET),
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_items(path: Path, expected_items: int, expected_sha256: str) -> int:
    rows = harness.load_items(path)
    if expected_items and len(rows) != expected_items:
        raise ValueError(f"{path}: expected {expected_items} items, found {len(rows)}")
    actual = file_sha256(path)
    if expected_sha256 and actual != expected_sha256.casefold():
        raise ValueError(
            f"{path}: SHA-256 mismatch: expected {expected_sha256}, found {actual}"
        )
    print(f"verified {len(rows)} items; sha256={actual}")
    return len(rows)


def summarize(root: Path, chosen: list[str]) -> int:
    print(
        f"\n{'model':<20}{'items':>7}{'pass':>6}{'fail':>6}"
        f"{'unres':>7}{'all-row':>11}{'resolved':>11}"
    )
    incomplete = False
    for model, name in MODELS.items():
        path = root / model.replace("/", "_") / "manifest.json"
        if not path.exists():
            if model in chosen:
                incomplete = True
                print(
                    f"{name:<20}{'-':>7}{'-':>6}{'-':>6}{'-':>7}"
                    f"{'ERROR':>11}{'ERROR':>11}"
                )
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        counts = manifest["counts"]
        all_row = manifest["task_success_rate_all_rows"]
        resolved = manifest["semantic_accuracy_resolved"]
        print(
            f"{name:<20}{manifest['n_items']:>7}{counts.get('pass', 0):>6}"
            f"{counts.get('fail', 0):>6}{counts.get('unresolved', 0):>7}"
            f"{all_row:>10.1%}"
            f"{format(resolved, '.1%') if resolved is not None else 'n/a':>11}"
        )
    return 1 if incomplete else 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Arguments after -- go to harness.py, e.g. -- --concurrency 4.\n"
            "Output budgets of the paper's primary requests are passed by default:\n"
            f"  subject {DEFAULT_SUBJECT_BUDGET} tokens ("
            + ", ".join(f"{MODELS[m]} {n}" for m, n in SUBJECT_BUDGETS.items())
            + f"), judge {JUDGE_BUDGET} tokens.\n"
            "Served through a first-party API in the paper (sent through OpenRouter here):\n  "
            + "\n  ".join(FIRST_PARTY_IN_PAPER.values())
            + "\nNot served through OpenRouter in the paper (run harness.py directly):\n  "
            + "\n  ".join(OTHER_ROUTES.values())
        ),
    )
    result.add_argument(
        "--items", type=Path, default=Path("data/eval.jsonl"),
        help="local OpenAI-format release JSONL (default: data/eval.jsonl)",
    )
    result.add_argument("--expected-items", type=int, default=1632)
    result.add_argument(
        "--expected-sha256", default="",
        help="optional published SHA-256; mismatch stops before any API call",
    )
    result.add_argument("--models", action="append", choices=list(MODELS), metavar="ID")
    result.add_argument("--out", type=Path, default=Path("runs"))
    result.add_argument("--limit", type=int, default=0, help="smoke-test first N items")
    return result


def main() -> int:
    known, rest = parser().parse_known_args()
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not known.items.exists():
        chunked = known.items.with_suffix(".parts")
        hint = (
            f" This tree stores it as {chunked}/; run `python reconstruct_artifact.py"
            " --artifact-dir . --out-dir reconstructed` and run this script inside"
            " reconstructed/, or pass --items."
            if chunked.is_dir() else " Pass --items."
        )
        raise SystemExit(f"missing {known.items}.{hint}")
    try:
        verify_items(known.items, known.expected_items, known.expected_sha256)
    except (OSError, ValueError, TypeError) as error:
        raise SystemExit(str(error)) from None
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("set OPENROUTER_API_KEY; no API request was made")

    chosen = known.models or list(MODELS)
    root = known.out / f"limit{known.limit}" if known.limit else known.out
    items = known.items
    if known.limit:
        rows = harness.load_items(known.items)[: known.limit]
        root.mkdir(parents=True, exist_ok=True)
        items = root / "items.jsonl"
        harness.write_jsonl(items, rows)

    for number, model in enumerate(chosen, 1):
        arguments = harness.parser().parse_args([
            "--items", str(items),
            "--out", str(root / model.replace("/", "_")),
            "--subject-model", model,
            "--judge-model", PRIMARY_JUDGE,
            "--secondary-judge-model", SECONDARY_JUDGE,
            *budget_arguments(model),
            *rest,
        ])
        print(f"=== [{number}/{len(chosen)}] {MODELS[model]} -> {arguments.out}")
        try:
            harness.run(arguments)
        except Exception as error:  # preserve the other model runs
            print(f"!!! {MODELS[model]} failed: {type(error).__name__}: {error}")
    return summarize(root, chosen)


if __name__ == "__main__":
    raise SystemExit(main())
