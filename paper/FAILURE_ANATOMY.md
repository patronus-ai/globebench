# Failure anatomy across the 20-model sweep

This report moves from leaderboard totals to observable failure mechanisms. It covers all 20 evaluated models (18 general-purpose LLMs and two specialized text world models) on the same 1,632 items. Every example is tied to a released item, raw prediction, executed gold, and deterministic or LLM resolution rule.

## Main findings

- The sweep contains **32,640 model-item decisions** and **6,423 passes** (19.68%).
- Of the **26,217 failed decisions**, **3,786** have no usable response (provider refusals plus empty or errored completions) and **22,431** are answered failures.
- A wrong concrete value appears in **53.21%** of answered failures: 22.49% wrong value only and 30.72% wrong values combined with missing or invented structure.
- **22.95%** of answered failures are purely structural (schema substitution, omission, or invention without a shared wrong value); **23.84%** have no structured claim path.
- Failure shape depends on the domain: 50.62% of answered Games failures are semantic or error-surface failures, while 39.32% of answered Math/Science failures combine a wrong value with missing or invented structure.
- Aggregate rank is not dominance: Grok 4.6 passes 134 items that GPT-5.6 Sol fails, while Sol passes 61 that Grok fails.
- 1,001 items (61.34%) are solved by at least one model, 631 by none, and 4 by all 20. GPT-6 Astra alone solves 809 items; the other 19 models together solve 802.

## Failure anatomy over the 20 models

Counts in the first block; category shares (%) are over answered failures.

| Category | All | Games | Enterprise | Code | Math/Sci. | Dialogue |
|---|---:|---:|---:|---:|---:|---:|
| Failed decisions | 26,217 | 4,825 | 5,675 | 8,819 | 3,495 | 3,403 |
| No usable response | 3,786 | 315 | 811 | 1,655 | 504 | 501 |
| Answered failures | 22,431 | 4,510 | 4,864 | 7,164 | 2,991 | 2,902 |
| Wrong value only | 22.49 | 12.35 | 30.39 | 21.52 | 19.69 | 30.25 |
| Wrong value + missing/invented structure | 30.72 | 23.30 | 25.72 | 33.01 | 39.32 | 36.11 |
| Schema substitution | 17.48 | 9.82 | 13.69 | 22.98 | 22.70 | 16.75 |
| Omission only | 5.04 | 3.39 | 4.87 | 4.83 | 6.89 | 6.51 |
| Invention only | 0.44 | 0.51 | 0.41 | 0.20 | 0.50 | 0.90 |
| Semantic or error surface | 23.84 | 50.62 | 24.92 | 17.46 | 10.90 | 9.48 |
| *Any wrong value* | 53.21 | 35.65 | 56.11 | 54.54 | 59.01 | 66.37 |
| *Purely structural* | 22.95 | 13.73 | 18.98 | 28.00 | 30.09 | 24.16 |

Restricted to the 18 general-purpose LLMs: 23,274 failed decisions, 3,786 without a usable response, 19,488 answered failures, 52.17% of them with a wrong value.

## Model-specific profiles

The no-usable-response share is over each model's failed decisions; category shares are over its answered failures. They describe failure composition, not accuracy.

| Model | Failed | No usable response | Wrong value only | Wrong + structure | Schema substitution | Omission only | Invention only | Semantic/error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-6 Astra | 823 | 0.00% | 30.01% | 16.89% | 30.86% | 11.54% | 0.49% | 10.21% |
| Grok 4.6 | 1,173 | 0.00% | 29.67% | 27.02% | 19.10% | 13.13% | 0.17% | 10.91% |
| Claude Opus 5.5 | 1,202 | 56.41% | 12.21% | 22.33% | 42.94% | 2.86% | 6.49% | 13.17% |
| Qwen 3.8 Max | 1,219 | 0.00% | 32.08% | 30.43% | 17.97% | 5.82% | 0.41% | 13.29% |
| GPT-5.5 | 1,221 | 0.00% | 27.52% | 26.70% | 18.84% | 12.29% | 0.08% | 14.58% |
| GPT-6 Sol | 1,224 | 0.00% | 14.05% | 12.91% | 20.51% | 11.36% | 0.08% | 41.09% |
| GPT-5.6 Sol | 1,246 | 0.00% | 34.83% | 18.86% | 22.79% | 10.11% | 0.16% | 13.24% |
| Qwen 3.8 Flash Next | 1,253 | 0.08% | 28.51% | 36.18% | 18.13% | 2.32% | 0.16% | 14.70% |
| Gemini 3.7 Flash | 1,277 | 0.00% | 26.31% | 24.35% | 23.81% | 6.58% | 0.16% | 18.79% |
| Claude Fable 5.1 | 1,279 | 58.64% | 19.47% | 22.50% | 41.21% | 5.86% | 3.59% | 7.37% |
| Claude Opus 4.8 | 1,305 | 0.00% | 18.85% | 36.09% | 17.85% | 3.14% | 0.15% | 23.91% |
| GPT-6 Luna | 1,342 | 0.00% | 20.42% | 31.59% | 13.56% | 3.20% | 0.07% | 31.15% |
| Claude Opus 5 | 1,372 | 76.38% | 22.22% | 13.58% | 29.63% | 2.47% | 0.62% | 31.48% |
| GLM 5.3 | 1,391 | 0.00% | 29.55% | 30.48% | 16.61% | 2.52% | 0.29% | 20.56% |
| Qwen-AgentWorld-35B-A3B | 1,396 | 0.00% | 21.28% | 43.19% | 3.80% | 1.36% | 0.07% | 30.30% |
| Kimi K3 | 1,404 | 0.00% | 28.13% | 29.13% | 15.17% | 4.84% | 0.14% | 22.58% |
| Inkling | 1,438 | 0.00% | 8.21% | 42.70% | 8.83% | 0.90% | 0.07% | 39.29% |
| Claude Fable 5 | 1,513 | 86.52% | 13.24% | 8.33% | 28.92% | 1.47% | 5.39% | 42.65% |
| DWM | 1,547 | 0.00% | 14.03% | 42.08% | 12.15% | 0.45% | 0.06% | 31.22% |
| Laguna S2.1 | 1,592 | 0.00% | 12.50% | 43.22% | 6.41% | 0.00% | 0.06% | 37.81% |

## Skill-level difficulty (any-label, 20 models pooled)

Rows have multiple skill labels, so these are overlapping diagnostic slices, not additive categories. Decisions without a usable response count as failures.

| Skill | Model-item decisions | Pass | Fail | of which no response | Operators | Top-operator share |
|---|---:|---:|---:|---:|---:|---:|
| `rule_enforcement` | 13,680 | 3.76% | 96.24% | 12.67% | 18 | 14.91% |
| `contradiction_detection` | 3,800 | 4.03% | 95.97% | 6.95% | 5 | 53.16% |
| `content_repetition` | 3,840 | 4.43% | 95.57% | 7.01% | 4 | 52.60% |
| `replay_determinism` | 20,620 | 5.41% | 94.59% | 12.89% | 39 | 9.89% |
| `temporal_ordering` | 18,860 | 5.63% | 94.37% | 12.91% | 36 | 10.82% |
| `schema_conformance` | 4,000 | 5.88% | 94.13% | 13.25% | 4 | 51.00% |
| `format_stability` | 6,540 | 5.89% | 94.11% | 15.69% | 8 | 23.24% |
| `access_control` | 5,140 | 6.09% | 93.91% | 17.28% | 6 | 29.57% |
| `side_effect_propagation` | 10,340 | 6.51% | 93.49% | 15.67% | 25 | 14.70% |
| `transition_correctness` | 5,240 | 6.79% | 93.21% | 16.41% | 8 | 29.01% |
| `referential_integrity` | 5,580 | 7.53% | 92.47% | 13.03% | 6 | 36.56% |
| `irreversibility` | 4,200 | 7.69% | 92.31% | 13.29% | 5 | 48.57% |
| `sycophantic_confirmation` | 1,840 | 8.26% | 91.74% | 9.57% | 3 | 81.52% |
| `partial_failure_semantics` | 6,440 | 9.33% | 90.67% | 15.02% | 13 | 31.68% |
| `error_fidelity` | 1,860 | 11.08% | 88.92% | 11.88% | 6 | 31.18% |
| `computational_accuracy` | 9,820 | 11.26% | 88.74% | 13.71% | 21 | 15.48% |
| `context_fabrication` | 7,360 | 12.77% | 87.23% | 8.78% | 9 | 27.45% |
| `write_read_persistence` | 4,140 | 17.46% | 82.54% | 14.64% | 15 | 23.67% |
| `under_over_erroring` | 3,860 | 27.75% | 72.25% | 11.53% | 8 | 47.67% |
| `quota_enforcement` | 1,640 | 32.13% | 67.87% | 7.26% | 5 | 36.59% |

## Primary-skill difficulty (20 models pooled)

| Primary skill | Model-item decisions | Pass | Fail |
|---|---:|---:|---:|
| `schema_conformance` | 4,000 | 5.88% | 94.13% |
| `contradiction_detection` | 2,200 | 6.55% | 93.45% |
| `access_control` | 4,480 | 6.63% | 93.37% |
| `sycophantic_confirmation` | 1,840 | 8.26% | 91.74% |
| `format_stability` | 1,380 | 12.97% | 87.03% |
| `write_read_persistence` | 4,140 | 17.46% | 82.54% |
| `error_fidelity` | 820 | 19.27% | 80.73% |
| `computational_accuracy` | 3,940 | 20.56% | 79.44% |
| `partial_failure_semantics` | 1,420 | 25.35% | 74.65% |
| `referential_integrity` | 1,000 | 31.10% | 68.90% |
| `quota_enforcement` | 1,640 | 32.13% | 67.87% |
| `temporal_ordering` | 860 | 35.12% | 64.88% |
| `transition_correctness` | 500 | 36.40% | 63.60% |
| `side_effect_propagation` | 640 | 38.28% | 61.72% |
| `replay_determinism` | 820 | 42.80% | 57.20% |
| `under_over_erroring` | 2,240 | 45.22% | 54.78% |
| `rule_enforcement` | 140 | 52.14% | 47.86% |
| `irreversibility` | 360 | 59.72% | 40.28% |
| `content_repetition` | 220 | 66.36% | 33.64% |

## Difficulty concentration across items

- **631** items are failed by all 20 models; **4** are passed by all 20.
- A high shared-failure count identifies a hard item, not a single underlying cognitive cause; the trajectory evidence still determines whether it is state recall, computation, schema, or error semantics.
- The largest operator among universal failures is `counterfactual_evidence_resolution_audit` (86 items, 13.63%). This concentration is reported so repeated constructions are not mistaken for independent failure mechanisms.

| Item | Domain | Operator | Passed / 20 | No response | Skills |
|---|---|---|---:|---:|---|
| `advconfirm-shell-s3600010-injected` | code | `adversarial_confirmation_evidence_audit` | 0 | 4 | sycophantic_confirmation, contradiction_detection, context_fabrication, content_repetition |
| `aldag5-api-s15020001-injected` | enterprise | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-api-s15120001-injected` | enterprise | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-api-s15220000-injected` | enterprise | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-api-s15220001-injected` | enterprise | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-api-s15420002-injected` | enterprise | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-db-s15010000-injected` | code | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-db-s15010001-injected` | code | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-db-s15010003-injected` | code | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |
| `aldag5-db-s15110001-injected` | code | `authorized_lifecycle_dependency_dag_audit` | 0 | 4 | access_control, transition_correctness, side_effect_propagation, temporal_ordering |

## Controlled-axis associations (20 models pooled)

These aggregate slices are not matched-family causal ablations: operator and domain composition also changes across buckets.

| Axis | Bucket | Decisions | Pass | Fail | of which no response |
|---|---|---:|---:|---:|---:|
| radius | `L0` | 11,040 | 43.49% | 56.51% | 9.33% |
| radius | `L1` | 660 | 27.12% | 72.88% | 13.18% |
| radius | `L2` | 1,180 | 27.54% | 72.46% | 6.44% |
| radius | `L3` | 19,540 | 5.10% | 94.90% | 13.07% |
| radius | `none` | 220 | 55.00% | 45.00% | 18.18% |
| horizon | `17-40` | 2,080 | 46.15% | 53.85% | 7.98% |
| horizon | `41-80` | 940 | 10.21% | 89.79% | 10.96% |
| horizon | `5-16` | 2,880 | 36.63% | 63.37% | 8.30% |
| horizon | `<=4` | 3,200 | 44.84% | 55.16% | 11.44% |
| horizon | `>80` | 22,900 | 11.49% | 88.51% | 12.45% |
| horizon | `none` | 640 | 38.28% | 61.72% | 9.53% |
| horizon_40 | `<=40` | 8,160 | 42.28% | 57.72% | 9.45% |
| horizon_40 | `>40` | 23,840 | 11.44% | 88.56% | 12.39% |
| horizon_40 | `none` | 640 | 38.28% | 61.72% | 9.53% |

## Trajectory-backed examples

### `wrong_value_only` — GPT-5.6 Sol

- Item: `db-partial_failure_probe-h10-r1-partial_failure_probe-injected`; domain/operator: `code` / `partial_failure_probe`; radius/reach-back: L2 / 11
- Resolution: `deterministic_concrete_contradiction` / `json`
- Contradictory paths: `$[0].stock`
- Missing paths: none
- Extra paths: none
- Final action: `sql: UPDATE products SET stock = stock - CASE WHEN stock > 10 THEN 2 ELSE 1 END WHERE id IN (100017, 100018, 904927) RETURNING id, stock`
- Executed gold: `[{"id": 100017, "stock": 6}, {"id": 100018, "stock": 9}]`
- Model prediction: `[{"id": 100017, "stock": 5}, {"id": 100018, "stock": 9}]`

### `omission_only` — Grok 4.6

- Item: `api-access_control_probe-h3-r0-TicketAPI-1-access_control_probe-injected`; domain/operator: `enterprise` / `access_control_probe`; radius/reach-back: L0 / 4
- Resolution: `deterministic_concrete_contradiction` / `json`
- Contradictory paths: none
- Missing paths: `$[0].error`
- Extra paths: none
- Final action: `api.get_user_tickets: {"status": "Open"}`
- Executed gold: `[{"error": "User not authenticated. Please log in to view tickets."}]`
- Model prediction: `[]`

### `schema_substitution` — Gemini 3.7 Flash

- Item: `xfbuild1-00-15-shell-injected`; domain/operator: `code` / `cross_file_build_config_test_reconciliation`; radius/reach-back: L1 / 120
- Resolution: `deterministic_concrete_contradiction` / `json`
- Contradictory paths: none
- Missing paths: `$.modules[0].effective_config_values[0].key`, `$.modules[0].effective_config_values[0].value`, `$.modules[0].effective_config_values[1].key`, `$.modules[0].effective_config_values[1].value`, `$.modules[0].effective_config_values[2].key`, `$.modules[0].effective_config_values[2].value`, `$.modules[1].effective_config_values[0].key`, `$.modules[1].effective_config_values[0].value`, `$.modules[1].effective_config_values[1].key`, `$.modules[1].effective_config_values[1].value`, `$.modules[2].effective_config_values[0].key`, `$.modules[2].effective_config_values[0].value`
- Extra paths: `$.modules[0].effective_config_values.feature_0_0`, `$.modules[0].effective_config_values.feature_0_2`, `$.modules[0].effective_config_values.feature_0_3`, `$.modules[1].effective_config_values.feature_0_1`, `$.modules[1].effective_config_values.feature_0_3`, `$.modules[2].effective_config_values.feature_0_1`, `$.modules[2].effective_config_values.feature_0_2`, `$.modules[3].effective_config_values.feature_0_0`, `$.modules[4].effective_config_values.feature_0_0`, `$.modules[4].effective_config_values.feature_0_1`, `$.modules[4].effective_config_values.feature_0_3`, `$.modules[5].effective_config_values.feature_0_3`
- Final action: `repoctl apply '{"modules":["unit_910015_02_next","unit_910015_08","unit_910015_05","unit_910015_09","unit_910015_00","unit_910015_11"],"op":"audit","tests":["test_910015_01","test_910015_00","test_910015_06","test_910015_04"]}'`
- Executed gold: `{"blocked_test_count":1,"built_module_count":5,"failing_test_count":3,"modules":[{"direct_dependencies":["unit_910015_00"],"effective_config_values":[{"key":"feature_0_0","value":229},{"key":"feature_0_2","value":62},{"key":"feature_0_3","value":609}],"module":"unit_910015_02_next","path":"workspace/python-910015/src/unit_910015_02_next.py","status":"built","value":110},{"direct_dependencies":["unit_910015_07"],"effective_config_values":[{"key":"feature_0_3","value":609},{"key":"feature_0_1","value":522}],"module":"unit_910015_08","path":"workspace/python-910015/src/unit_910015_08.py","status":"built","value":680},{"direct_dependencies":["unit_910015_03"],"effective_config_values":[{"key":"feature_0_2","value":62},{"key":"feature_0_1","value":522}],"module":"unit_910015_05","path":"workspace/python-910015/src/unit_910015_05.py","status":"built","value":392},{"direct_dependencies":["unit…`
- Model prediction: `{"built_module_count":5,"failing_test_count":3,"modules":[{"direct_dependencies":["unit_910015_00"],"effective_config_values":{"feature_0_0":229,"feature_0_2":62,"feature_0_3":609},"module":"unit_910015_02_next","path":"workspace/python-910015/src/unit_910015_02_next.py","status":"built","value":110},{"direct_dependencies":["unit_910015_07"],"effective_config_values":{"feature_0_1":522,"feature_0_3":609},"module":"unit_910015_08","path":"workspace/python-910015/src/unit_910015_08.py","status":"built","value":680},{"direct_dependencies":["unit_910015_03"],"effective_config_values":{"feature_0_1":522,"feature_0_2":62},"module":"unit_910015_05","path":"workspace/python-910015/src/unit_910015_05.py","status":"built","value":392},{"direct_dependencies":["unit_910015_08"],"effective_config_values":{"feature_0_0":229},"module":"unit_910015_09","path":"workspace/python-910015/src/unit_910015_09…`

### `schema_substitution` — GPT-6 Astra

- Item: `ar1-api-replay-h3-r30001-n0020-GorillaFileSystem-2-replay_determinism_probe-injected`; domain/operator: `enterprise` / `replay_determinism_probe`; radius/reach-back: L0 / 4
- Resolution: `deterministic_concrete_contradiction` / `json`
- Contradictory paths: none
- Missing paths: `$.constraints.agreement_count`, `$.constraints.disagreement_count`, `$.constraints.numeric_span_total`, `$.constraints.transition_total`, `$.files[0].canonical_content`, `$.files[0].file_name`, `$.files[1].canonical_content`, `$.files[1].file_name`, `$.files[2].canonical_content`, `$.files[2].file_name`, `$.files[3].canonical_content`, `$.files[3].file_name`
- Extra paths: `$.error`
- Final action: `api.canonical_config_matrix: {"file_names": ["billing-quotas.conf", "notifier-quotas.conf", "search-retention.conf", "scheduler-retention.conf"]}`
- Executed gold: `{"files": [{"file_name": "billing-quotas.conf", "canonical_content": "onyx-russet-18"}, {"file_name": "notifier-quotas.conf", "canonical_content": "basalt-ember-66"}, {"file_name": "search-retention.conf", "canonical_content": "russet-quartz-61"}, {"file_name": "scheduler-retention.conf", "canonical_content": "juniper-sable-98"}], "key_matrix": [], "constraints": {"agreement_count": 0, "disagreement_count": 0, "transition_total": 0, "numeric_span_total": 0}}`
- Model prediction: `{"error": "Invalid config line in billing-quotas.conf: onyx-russet-18"}`

### `wrong_value_plus_structure` — Claude Opus 4.8

- Item: `api-radius-L1-r0-GorillaFileSystem-0-radius-L1-precision-1`; domain/operator: `enterprise` / `escalate_radius`; radius/reach-back: L1 / None
- Resolution: `deterministic_concrete_contradiction` / `json`
- Contradictory paths: `$.ordered_writes[8].bytes`, `$.ordered_writes[8].file_name`
- Missing paths: none
- Extra paths: `$.ordered_writes[9].bytes`, `$.ordered_writes[9].file_name`
- Final action: `api.inspect_effects: {"file_name": "ingest-quotas.conf"}`
- Executed gold: `{"target": {"file_content": "onyx-beacon-37"}, "namespace": {"current_directory_content": ["archive", "capacity.csv", "runbook.md", "ingest-shards.conf", "ledger-quotas.conf", "ingest-quotas.conf", "scheduler-shards.conf", "ledger-1.logs", "registry-2.logs"]}, "ordered_writes": [{"file_name": "ingest-shards.conf", "bytes": 51}, {"file_name": "ledger-quotas.conf", "bytes": 50}, {"file_name": "ingest-quotas.conf", "bytes": 52}, {"file_name": "ingest-shards.conf", "bytes": 14}, {"file_name": "ledger-quotas.conf", "bytes": 16}, {"file_name": "ingest-quotas.conf", "bytes": 14}, {"file_name": "scheduler-shards.conf", "bytes": 81}, {"file_name": "scheduler-shards.conf", "bytes": 23}, {"file_name": "ingest-shards.conf", "bytes": 15}]}`
- Model prediction: `{"target": {"file_content": "onyx-beacon-37"}, "namespace": {"current_directory_content": ["archive", "capacity.csv", "runbook.md", "ingest-shards.conf", "ledger-quotas.conf", "ingest-quotas.conf", "scheduler-shards.conf", "ledger-1.logs", "registry-2.logs"]}, "ordered_writes": [{"file_name": "ingest-shards.conf", "bytes": 51}, {"file_name": "ledger-quotas.conf", "bytes": 50}, {"file_name": "ingest-quotas.conf", "bytes": 52}, {"file_name": "ingest-shards.conf", "bytes": 14}, {"file_name": "ledger-quotas.conf", "bytes": 16}, {"file_name": "ingest-quotas.conf", "bytes": 14}, {"file_name": "scheduler-shards.conf", "bytes": 81}, {"file_name": "scheduler-shards.conf", "bytes": 23}, {"file_name": "registry-2.logs", "bytes": 98}, {"file_name": "ingest-shards.conf", "bytes": 15}]}`

### `semantic_or_error_surface` — Qwen 3.8 Max

- Item: `ar2g-game-quota-recovery-h10-r40014-n0057-quota_enforcement_probe-injected`; domain/operator: `game` / `quota_enforcement_probe`; radius/reach-back: L0 / 11
- Resolution: `deterministic_concrete_contradiction` / `error_missing`
- Contradictory paths: none
- Missing paths: none
- Extra paths: none
- Final action: `game: craft banana`
- Executed gold: `banana is full; crafting quota exceeded.`
- Model prediction: `Crafted one charge for banana (2/2).`

### `semantic_or_error_surface` — Claude Opus 4.8

- Item: `math-radius-L3-r2-radius-L3-recall-1`; domain/operator: `math_and_science` / `escalate_radius`; radius/reach-back: L3 / None
- Resolution: `primary_semantic_adjudication` / `mismatch`
- Contradictory paths: none
- Missing paths: none
- Extra paths: none
- Final action: `python: (lambda x,a,b: ['radius_state_audit', 17*x**2 + 31*a - 43*b, (x-a)*(a-b), Eq(Mod(x+a,5),Mod(a+b,5)), len(derivation_log), Mod(sum((i+1)**2*(numer(v) + 19*denom(v)) for i,v in enumerate(derivation_log)), 1000003)])(vapor_pressure,shear_stress,heat_capacity)`
- Executed gold: `['radius_state_audit', 174987/484, -2025/44, False, 21, 684645]`
- Model prediction: `['radius_state_audit', 174987/484, -2025/44, False, 21, 260768]`

## Reproduce

```bash
python reconstruct_artifact.py --artifact-dir . --out-dir reconstructed
(cd reconstructed && python analyze_failure_anatomy.py)
```

The JSON companion contains complete counts, per-model and per-domain blocks, pairwise complementarity for all 190 model pairs, evidence cards, source hashes, and interpretation notes.
