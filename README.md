# GlobeBench

Code, data, model outputs, and judge records for the paper "GlobeBench:
Evaluating Text-Based World Model Capabilities for Scalable Environment
Simulations" by Nicholas Saban, Charvi Bannur, Mariya Vasileva, and Darshan
Deshpande (Patronus AI).

GlobeBench measures whether a model can act as a text world model: given a
frozen, pre-rendered trajectory of actions and environment observations, it
must predict the environment's next observation. The benchmark has 1,632
execution-grounded items in five domains (Code, Enterprise, Games, Math and
Science, Dialogue).

This repository holds everything needed to audit and rescore the paper's
results without querying a model again:

- `data/eval.jsonl`: the 1,632 released items (SHA-256
  `99cc6b668c9c4227bd6dd73b4717f935594de32cbfb9d8a72ad8a76dec569304`), stored
  in this tree as row-boundary parts under `data/eval.parts/` and rebuilt by
  `reconstruct_artifact.py` (see "Artifact layout and verification"), and
  `data/judge_scoring_contracts.jsonl`, the scoring contract the response
  judge received for the 606 items whose `metadata.scoring` is empty (see
  "Scoring protocol");
- `runs/`: for each of the 20 evaluated models, every subject response, every
  LLM judge record, and the fused per-item decision;
- `paper/`: the leaderboard, the failure anatomy, and the full-corpus LLM
  quality audit;
- `harness.py`, `deterministic_grader.py`, `reproduce.py`: a self-contained
  runner and the deterministic grader;
- `rescore_offline.py`, `analyze_failure_anatomy.py`: offline rescoring and
  the failure analysis.

The paper evaluates 20 models: 18 general-purpose LLMs and two specialized
text world models, Qwen-AgentWorld-35B-A3B and the Digital World Model (DWM).
That is 32,640 model-item decisions, of which 28,854 have a usable response.
All models were evaluated on the same items and rendered prompts with grader
`wm-grader-1.5`, hybrid policy `wm-hybrid-deterministic-llm/2`, judge prompt
`wm-response-judge/4`, and the same judge models and settings.

## Leaderboard

Task success is passes over all 1,632 items. A row without a usable response
(a provider refusal or an empty or errored completion) is a failure and stays
in the denominator. Pooled success divides all passes by 20 x 1,632, which
equals the mean of the per-model rates. Percentages are rounded half-up.

| Rank | Model | Pass | Task success | Refusals | Other non-responses |
|---:|---|---:|---:|---:|---:|
| 1 | GPT-6 Astra | 809 | 49.57% | 0 | 0 |
| 2 | Grok 4.6 | 459 | 28.13% | 0 | 0 |
| 3 | Claude Opus 5.5 | 430 | 26.35% | 675 | 3 |
| 4 | Qwen 3.8 Max | 413 | 25.31% | 0 | 0 |
| 5 | GPT-5.5 | 411 | 25.18% | 0 | 0 |
| 6 | GPT-6 Sol | 408 | 25.00% | 0 | 0 |
| 7 | GPT-5.6 Sol | 386 | 23.65% | 0 | 0 |
| 8 | Qwen 3.8 Flash Next | 379 | 23.22% | 0 | 1 |
| 9 | Gemini 3.7 Flash | 355 | 21.75% | 0 | 0 |
| 10 | Claude Fable 5.1 | 353 | 21.63% | 668 | 82 |
| 11 | Claude Opus 4.8 | 327 | 20.04% | 0 | 0 |
| 12 | GPT-6 Luna | 290 | 17.77% | 0 | 0 |
| 13 | Claude Opus 5 | 260 | 15.93% | 1,044 | 4 |
| 14 | GLM 5.3 | 241 | 14.77% | 0 | 0 |
| 15 | Qwen-AgentWorld-35B-A3B | 236 | 14.46% | 0 | 0 |
| 16 | Kimi K3 | 228 | 13.97% | 0 | 0 |
| 17 | Inkling | 194 | 11.89% | 0 | 0 |
| 18 | Claude Fable 5 | 119 | 7.29% | 1,309 | 0 |
| 19 | Digital World Model (DWM) | 85 | 5.21% | 0 | 0 |
| 20 | Laguna S2.1 | 40 | 2.45% | 0 | 0 |
| | **All 20 (pooled)** | **6,423 / 32,640** | **19.68%** | **3,696** | **90** |

Machine-readable form: `paper/FINAL_BINARY_LEADERBOARD.json`.

## Models and run directories

Each model has a subject directory (`results.jsonl`, plus a `manifest.json`
for every model except GPT-5.6 Sol), a fused-score directory
(`hybrid_scores.jsonl`, `summary.json`, `paper_table.{csv,md}`), and judge
directories, all under `runs/`. Each judge directory holds `judgments.jsonl`
and a `summary.json` or `manifest.json`, except
`final_judge_qwen_agentworld_primary`, which holds only `judgments.jsonl`.
The `model_key` column is the key used in the rows. The judge directories hold
Terra (primary) and Sol (fallback) records keyed by `subject_model_key`.
Some files also hold records for an earlier response to a row that was later
re-requested; `rescore_offline.py` uses the record bound to the released
prediction.

| Model | `model_key` | Subject | Fused scores | Judge records |
|---|---|---|---|---|
| GPT-6 Astra | `openai/gpt-6-astra` | `subject_gpt6astra` | `hybrid_gpt6astra` | `final_judge_gpt6astra` |
| Grok 4.6 | `xai/grok-4.6` | `subject_grok46` | `hybrid_grok46` | `judge_terra_initial`, `judge_sol_secondary` |
| Claude Opus 5.5 | `anthropic/claude-opus-5.5` | `subject_opus55` | `hybrid_opus55` | `final_judge_opus55`, `final_judge_opus55_secondary` |
| Qwen 3.8 Max | `qwen/qwen3.8-max` | `subject_qwen38max` | `hybrid_qwen38max` | `judge_terra_initial`, `final_judge_qwen` |
| GPT-5.5 | `openai/gpt-5.5` | `subject_gpt55` | `hybrid_gpt55` | `judge_terra_initial`, `judge_sol_secondary` |
| GPT-6 Sol | `openai/gpt-6-sol` | `subject_gpt6sol` | `hybrid_gpt6sol` | `final_judge_gpt6sol` |
| GPT-5.6 Sol | `openai/gpt-5.6-sol` | `subject_sol` | `hybrid_sol` | `judge_terra_initial`, `judge_sol_secondary` |
| Qwen 3.8 Flash Next | `qwen/qwen3.8-flash-next` | `subject_qwen38flashnext` | `hybrid_qwen38flashnext` | `final_judge_qwen38flashnext` |
| Gemini 3.7 Flash | `google/gemini-3.7-flash` | `subject_gemini37flash` | `hybrid_gemini37flash` | `judge_terra_initial`, `judge_sol_secondary`, `final_judge_gemini` |
| Claude Fable 5.1 | `anthropic/claude-fable-5.1` | `subject_fable51` | `hybrid_fable51` | `final_judge_fable51` |
| Claude Opus 4.8 | `anthropic/claude-opus-4.8` | `subject_opus48` | `hybrid_opus48` | `judge_terra_initial`, `judge_sol_secondary` |
| GPT-6 Luna | `openai/gpt-6-luna` | `subject_gpt6luna` | `hybrid_gpt6luna` | `final_judge_gpt6luna`, `final_judge_gpt6luna_secondary` |
| Claude Opus 5 | `anthropic/claude-opus-5` | `subject_opus5` | `hybrid_opus5` | `final_judge_opus5` |
| GLM 5.3 | `zhipu/glm-5.3` | `subject_glm53` | `hybrid_glm53` | `judge_terra_initial`, `judge_sol_secondary`, `final_judge_glm` |
| Qwen-AgentWorld-35B-A3B | `external/qwen-agentworld-35b-a3b` | `external_qwen_agentworld` | `external_hybrid_final/qwen-agentworld` | `external_judge_terra`, `external_judge_sol`, `final_judge_qwen_agentworld_primary` |
| Kimi K3 | `moonshot/kimi-k3` | `subject_kimi_k3` | `hybrid_kimi_k3` | `judge_terra_initial` |
| Inkling | `thinking_machines/inkling` | `subject_inkling` | `hybrid_inkling` | `judge_terra_initial`, `judge_sol_secondary`, `final_judge_inkling` |
| Claude Fable 5 | `anthropic/claude-fable-5` | `subject_fable5` | `hybrid_fable5` | `final_judge_fable5` |
| Digital World Model (DWM) | `external/dwm` | `external_dwm` | `external_hybrid_final/dwm` | `external_judge_terra`, `external_judge_sol` |
| Laguna S2.1 | `poolside/laguna-s-2.1` | `subject_laguna` | `hybrid_laguna` | `judge_terra_initial` |

## Serving settings

Each subject row records its route in `provider` and its request settings in
`params` (`max_tokens` is the output budget). The exception is 30 Claude Opus
4.8 rows, which record them in a `serving` object instead. The primary
requests used:

| Model | Route (`provider`) | Recorded settings | Output budget |
|---|---|---|---:|
| GPT-6 Astra | OpenAI API (`openai`) | reasoning effort high, seed 0 | 65,536 |
| GPT-6 Sol, GPT-6 Luna | OpenRouter pinned to OpenAI (`openrouter`) | reasoning effort high; no temperature or seed sent | 65,536 |
| Claude Opus 5, Opus 5.5, Fable 5, Fable 5.1 | OpenRouter pinned to Anthropic (`openrouter`) | reasoning effort high; no temperature or seed sent | 65,536 |
| Grok 4.6, Qwen 3.8 Max, GPT-5.5, Gemini 3.7 Flash, GLM 5.3, Kimi K3, Inkling | OpenRouter (`openrouter`) | reasoning effort high, temperature 0, seed 0 | 65,536 |
| Laguna S2.1 | OpenRouter (`openrouter`) | reasoning enabled, temperature 0, seed 0 | 65,536 |
| GPT-5.6 Sol | OpenAI API (`openai`) | `reasoning_effort` high, temperature 0, seed 0 | 32,000 (64,000 on 36 rows) |
| Claude Opus 4.8 | Anthropic API (`anthropic`) | adaptive thinking, effort high, temperature 0, seed 0 | 32,000 (64,000 on 137 rows; 128,000 with streaming on 30 rows recorded in `serving`) |
| Qwen 3.8 Flash Next | OpenAI-compatible endpoint (`self_hosted`) | thinking on with chat-template `reasoning_effort: xhigh`, temperature 1.0, top-p 0.95, top-k 20, seed 0 | 110,000 |
| Qwen-AgentWorld-35B-A3B, DWM | OpenAI-compatible endpoint (`self_hosted`) | temperature 0.6, top-p 0.95, top-k 20, seed 0 (Qwen-AgentWorld's published recipe) | 32,768 |

"Pinned" means `params.extra_body.provider.only` with fallbacks disabled.
`self_hosted` marks the OpenAI-compatible endpoints that served these three
models.

Requests that returned no usable answer (an empty completion, an output-limit
stop, or a provider or transport error) were re-requested; completed answers
and refusals were never resampled. Some re-requests used a lower reasoning
setting, a larger output budget, a pinned router provider, or a different route
(for example 24 Claude Opus 4.8 rows through OpenRouter and 5 GLM 5.3 rows
through the Z.ai API, recorded as `provider: zai`). Each such row records
the settings it ran with and its original request in `repair_provenance` or
`recovery_provenance`.

Model-key spelling: the rows use `moonshot/`, `zhipu/`, `xai/`, and
`thinking_machines/`, while `reproduce.py` uses the OpenRouter ids
`moonshotai/kimi-k3`, `z-ai/glm-5.3`, `x-ai/grok-4.6`, and
`thinkingmachines/inkling`.

## Scoring protocol

- Hybrid policy `wm-hybrid-deterministic-llm/2`; deterministic grader
  `wm-grader-1.5`; response-judge prompt `wm-response-judge/4`. `harness.py`
  runs the same policy, grader, and judge prompt.
- Every served response gets a deterministic analysis. The grader can certify
  equivalence (pass), certify a concrete contradiction (fail), or abstain.
- An abstention is decided by the primary judge, `openai/gpt-5.6-terra`.
  `openai/gpt-5.6-sol` retries a missing, malformed, uncertain, or
  low-confidence Terra judgment. Judge settings: temperature 0, seed 0, low
  reasoning, minimum confidence 0.80, 16,384 output tokens (recorded in each
  judge row's `judge_params`).
- Across the 28,854 usable responses, 24,483 decisions are deterministic
  (including 79 git-status adapter decisions), 4,365 come from Terra, and 6
  from the Sol fallback. Format compliance is reported separately and never
  changes semantic correctness.
- Judge prompt binding: `harness.judge_messages` renders the judge prompt
  exactly as in the evaluation runs, and a judge row's `prompt_sha256` is
  `harness.judge_prompt_sha256` of that prompt. For 606 items whose
  `metadata.scoring` is empty, `data/judge_scoring_contracts.jsonl` holds the
  scoring contract the judge received; `harness.py` reads that file when it
  sits next to `--items` (or pass `--judge-contracts`). `rescore_offline.py`
  checks that each of the 4,371 judge verdicts it applies is bound to the
  released item and prediction.
- Rows record a `grader_fingerprint` (the grader version plus a hash of its
  source) that identifies the grader build that wrote them. Re-grading every
  served response with the shipped `deterministic_grader.py` reproduces every
  stored decision.

## Refusals and other non-responses

- A refusal is a provider stop with `finish_reason: content_filter` (these
  rows also carry `refusal: true`). There are 3,696, all from four Claude models
  (Opus 5.5 675, Fable 5.1 668, Opus 5 1,044, Fable 5 1,309). 24 of them carry
  partial text (21 from Opus 5.5 and one from each other refusing model) and
  still count as refusals.
- 90 empty or errored completions: Fable 5.1 82, Opus 5 4, Opus 5.5 3, Qwen
  3.8 Flash Next 1.
- Both kinds count as failures with no credit and stay in every denominator.
  The fused rows label them `served_state` `empty_response`,
  `incomplete_or_refusal`, or `provider_error` with `semantic_outcome`
  `unresolved`; `rescore_offline.py` and the leaderboard count them as fails.
- Text written by the model is never counted as a refusal on its own.
- Refusal-excluded rates (Opus 5.5 44.93%, Fable 5.1 36.62%, Opus 5 44.22%,
  Fable 5 36.84%) are diagnostics only: they depend on which items each model
  chose to answer.
- `harness.py` is stricter than this rule: it also treats the finish reasons
  `refusal`, `safety`, and `blocked`, a provider refusal field, or a response
  that opens with a refusal phrase as `subject_refusal` and gives it no credit
  without grading it. The paper runs graded such responses like any other
  served response.

## Rescore without querying a model

A checkout is about 670 MB, and reconstruction writes about the same again. `rescore_offline.py`
reads the chunked tree directly, needs no network access, and runs in about
2-4 minutes on one CPU core.

```bash
python -m unittest discover -s tests -v
python rescore_offline.py            # works on this chunked tree
python reconstruct_artifact.py --artifact-dir . --out-dir reconstructed
(cd reconstructed && python analyze_failure_anatomy.py)
```

`rescore_offline.py` re-grades every served prediction with the shipped
grader, applies the stored Terra or Sol verdict wherever the grader abstains,
counts non-responses as failures, and compares each outcome with the released
fused decision. It also checks that each applied verdict's judge record is
bound to the released item and prediction by `prompt_sha256`. It prints the
20-row leaderboard and the number of bound verdicts, and exits non-zero on
any mismatch or unbound verdict. The git-status adapter, used on five
shell/code items (79 decisions in total), is not part of the shipped grader;
its stored decision is reused and reported separately.

`analyze_failure_anatomy.py` rebuilds `paper/FAILURE_ANATOMY.{md,json}`: the
20-model failure anatomy (26,217 failed decisions: 3,786 without a usable
response and 22,431 answered failures, 53.21% of which contain a wrong value),
per-model profiles, any-label and primary-skill slices, item difficulty, and
pairwise complementarity.

## Row formats

- Subject rows (`runs/subject_*`, `runs/external_*/results.jsonl`) contain the
  item id, `model_key`, `params`, `provider`, `prediction`, `gold`,
  `finish_reason`, `error`, token counts, latency, `grade_detail`,
  `decision`, and `grader_fingerprint`. Rows without a usable response are
  not graded: the 3,696 refusals and the 90 empty or errored completions
  have no `grade_detail`, and the 90 empty or errored rows also have no
  `grader_fingerprint`. The other exception is 30 Claude Opus 4.8
  rows served through the Anthropic API. They carry `serving` (effort,
  thinking, output budget, streaming) instead of `provider` and `params`, and
  a reduced field set: item id, `model_key`, `prediction`, `finish_reason`,
  token counts, latency, `decision`, and grader fields, without `gold`,
  `error`, `grade_detail`, item metadata, or `cache_key`. The fused rows and
  `data/eval.jsonl` supply the rest. Subject rows do not include the raw
  provider response object (`provider_output_omitted: true`); the
  model-visible `prediction` is the model's full answer.
- Re-requested rows carry `repair_provenance` (schema `wm-subject-repair/1`:
  original error, finish reason, and parameters) or `recovery_provenance`
  (original error, finish reason, prediction SHA-256, attempts). Rows with
  `recovery_provenance` also carry `provider_returned_model` (the model id
  reported by the router), and their refusal rows carry `refusal: true`.
- Judge rows (`judgments.jsonl`) are `wm-response-judge/4` records: verdict,
  semantic correctness, confidence, rationale, reason codes, prompt SHA-256,
  usage, the judge's raw text (`raw_response`), and in some rows the judge's
  provider message (`provider_output`). Router response objects and the
  providers' encrypted reasoning items are not included
  (`raw_response_omitted: true`, `reasoning_details_omitted: true`). A judge `summary.json` records
  `results_sha256`, the SHA-256 of the shipped `judgments.jsonl`; a judge
  `manifest.json` records `output_sha256` of the original output file.
- Fused rows (`hybrid_scores.jsonl`) record the deterministic evidence, judge
  states, `resolution_rule`, `semantic_outcome`, `format_outcome`, and
  `served_state`.
- Provenance fields in manifests and summaries (`items`, `results`, `base`,
  `source`, `repair_provenance.source`) refer to the original run files by
  role and SHA-256; those files are not part of the release. The shipped
  bytes are pinned by `DATA_INDEX.json` and `checksums.sha256`. `cache_key`
  is omitted from the rows of the three `self_hosted` models.

## Citation

```bibtex
@misc{saban2026globebench,
  title  = {{GlobeBench}: Evaluating Text-Based World Model Capabilities for Scalable Environment Simulations},
  author = {Saban, Nicholas and Bannur, Charvi and Vasileva, Mariya and Deshpande, Darshan},
  year   = {2026},
  note   = {arXiv preprint}
}
```

## Licensing

Copyright 2026 Patronus AI.

- The root `LICENSE` (Apache-2.0) covers the code and the item content we
  authored.
- `runs/`, `paper/`, and `data/judge_scoring_contracts.jsonl` are released
  under the same license, as far as our rights in them extend. `runs/`
  includes outputs generated by the evaluated models (served through provider
  APIs, OpenRouter, or self-hosted endpoints) and judge records generated by
  OpenAI models; use of those outputs may also be subject to the providers' or
  the models' license terms. Item content repeated in these records (for
  example `gold`) keeps the license of its item (see the table below).
- Each item records its source in `metadata.source`, and
  `metadata.source_license` records the license of the upstream source the
  item draws on. These labels are provenance metadata, not a legal conclusion
  that an item reproduces copyrightable upstream expression; preserve the
  attribution and notices the upstream licenses require.
- `THIRD_PARTY_NOTICES.md` lists each upstream project with its official URL,
  license, item count, and copyright notice, names the programs whose output
  the items quote, and includes the MIT, BSD-3-Clause, and Biopython license
  texts. The GPL-3.0 text is `LICENSES/GPL-3.0.txt`.

Of the 1,632 items, 1,137 come from our own recipes and record no upstream
source. The other 495 draw on an upstream project. BFCL, TextWorld,
tau2-bench, and the MCPMark trajectory logs supply data or structure that the
items adapt. SymPy (including one replayed doctest), SimPy, OpenSpiel,
python-chess, and SciPy, Cantera, RDKit, Astropy, and Biopython compute the
items' observations. The labels:

| `metadata.source_license` | Items | Meaning |
|---|---:|---|
| `Apache-2.0` | 1,162 | 955 items from our synthetic recipes, covered by the root `LICENSE`; 203 that adapt BFCL and 4 with observations computed by OpenSpiel, both Apache-2.0 |
| `MIT` | 250 | Items that adapt TextWorld (194), tau2-bench (36), or the MCPMark trajectory logs (17), and 3 with schedules computed by SimPy |
| `proprietary-none` | 182 | Items from our own recipes that record no upstream source; despite the label, they are covered by the root Apache-2.0 `LICENSE`. Some observations quote the output of the programs the items were executed against (see [Program output](THIRD_PARTY_NOTICES.md#program-output-quoted-in-items)). |
| `BSD-3-Clause` | 26 | Observations computed by SymPy; one item also replays a SymPy doctest |
| `mixed-permissive-see-contract` | 11 | Laboratory schedules simulated with SimPy (MIT) over measurements computed by SciPy, Cantera, RDKit, and Astropy (BSD-3-Clause) and Biopython (Biopython License Agreement); `THIRD_PARTY_NOTICES.md` lists the components and their licenses. |
| `GPL-3.0-or-later` | 1 | `csp-chess_parallel_board_reconciliation_audit-injected`, with observations computed by python-chess; this item is distributed under GPL-3.0-or-later (`LICENSES/GPL-3.0.txt`) |

## Run one model

Python 3.10+ with only the standard library. The only runtime credential is
read from an environment variable and is never written to an artifact. Run from a
reconstructed tree, where `data/eval.jsonl` exists:

```bash
python reconstruct_artifact.py --artifact-dir . --out-dir reconstructed
cd reconstructed
export OPENROUTER_API_KEY='...'
python harness.py \
  --items data/eval.jsonl \
  --out runs/example-model \
  --subject-model provider/model \
  --judge-model openai/gpt-5.6-terra \
  --secondary-judge-model openai/gpt-5.6-sol \
  --subject-max-tokens 65536 --judge-max-tokens 16384
```

The harness defaults are temperature 0, seed 0, high subject reasoning, low
judge reasoning, confidence threshold 0.8, eight concurrent items, and
output budgets of 4,096 (subject) and 1,024 (judge) tokens. Pass the budget of
the model's primary requests (Serving settings above; 65,536 for most models)
and 16,384 for the judge, as in the example. `--api-base` and `--api-key-env`
select another OpenAI-compatible endpoint. The harness always sends
temperature 0 and seed 0 and has no options for top-p, top-k, or chat-template
arguments. It therefore does not reproduce the recorded sampling of Qwen 3.8
Flash Next, Qwen-AgentWorld-35B-A3B, or DWM, or the later router-served
models' requests, which sent no temperature or seed.

Each output directory contains `results.jsonl` (one self-contained row per
item), `manifest.json` (configuration, hashes, and counts), and
`results.partial.jsonl` (a crash-resume ledger). Re-running the same command
resumes only rows whose run signature matches.

## Reproduce the paper sweep

`data/eval.jsonl` and each `runs/*/results.jsonl` exist only after
`reconstruct_artifact.py`; this tree stores large JSONL files as row-boundary
parts (next section). Run the driver inside the reconstructed tree:

```bash
python reconstruct_artifact.py --artifact-dir . --out-dir reconstructed
cd reconstructed
export OPENROUTER_API_KEY='...'
python reproduce.py --limit 5                      # smoke test
python reproduce.py --models openai/gpt-6-sol --limit 5
python reproduce.py \
  --expected-items 1632 \
  --expected-sha256 99cc6b668c9c4227bd6dd73b4717f935594de32cbfb9d8a72ad8a76dec569304
```

`reproduce.py` runs the 16 general-purpose LLMs reachable through OpenRouter. By
default it passes the output budgets of the paper's primary requests: 65,536
subject tokens (32,000 for GPT-5.6 Sol and Claude Opus 4.8) and 16,384 judge
tokens. Arguments after `--` go to `harness.py` and override these. In the
paper, GPT-5.6 Sol and Claude Opus 4.8 were served through their first-party
APIs; `reproduce.py` sends them through OpenRouter, so their reasoning
controls differ from the recorded ones.
GPT-6 Astra was served through the OpenAI API; run it with `harness.py` and
`--api-base https://api.openai.com/v1 --api-key-env OPENAI_API_KEY`. Qwen 3.8
Flash Next, Qwen-AgentWorld-35B-A3B, and DWM were served through
OpenAI-compatible endpoints; run them with
`harness.py` and `--api-base` pointing to such an endpoint. The harness does
not set OpenRouter provider pinning, so a re-run may be routed differently
from the paper's runs.

## Artifact layout and verification

Large JSONL files are split on row boundaries into
`<name>.parts/part-NNNN.jsonl`, so every file stays at or below 7 MiB and the
tree can be hosted in an ordinary Git repository without large-file storage.
`DATA_INDEX.json` maps each logical file to its parts and SHA-256,
`MANIFEST.json` lists the runs and counts, and `checksums.sha256` pins every
physical file.

```bash
sha256sum -c checksums.sha256
python reconstruct_artifact.py --artifact-dir . --out-dir reconstructed
```

`reconstruct_artifact.py` rejects path traversal, missing parts, and any
reconstructed file whose SHA-256 differs from `DATA_INDEX.json`.

- `data/`: the released items and `judge_scoring_contracts.jsonl`.
- `runs/`: subject, judge, and fused-score records per model (table above);
  `runs/llm_quality_audit` holds the two-phase LLM quality audit of every
  item's gold next state (1,632 score records, 1,627 of them complete, and
  `low_scores.jsonl`, the 395 items scored below 4 on some dimension).
- `paper/`: see `paper/INDEX.md` for what each file is.
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `LICENSES/`: see Licensing above.

