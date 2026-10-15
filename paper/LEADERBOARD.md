# GlobeBench leaderboard

All 20 models were evaluated on the same 1,632 items and rendered prompts with
the `wm-hybrid-deterministic-llm/2` policy, the `wm-grader-1.5` scorer, and the
same judge prompt and judges: 18 general-purpose LLMs and two specialized text
world models (marked ‡).

A row passes only when the subject returns a usable response that passes the
hybrid scorer. A row without a usable response (a provider refusal or an
empty or errored completion) is a failure and
stays in the denominator. Usable responses exist for 28,854 of the 32,640
model-item pairs; the other 3,786 are 3,696 provider refusals (†) and 90 empty
or errored completions. Percentages are rounded half-up.

| Rank | Model | Pass | Fail | Task success | Refusals | Other non-responses |
|---:|---|---:|---:|---:|---:|---:|
| 1 | GPT-6 Astra | 809 | 823 | 49.57% | 0 | 0 |
| 2 | Grok 4.6 | 459 | 1,173 | 28.13% | 0 | 0 |
| 3 | Claude Opus 5.5 † | 430 | 1,202 | 26.35% | 675 | 3 |
| 4 | Qwen 3.8 Max | 413 | 1,219 | 25.31% | 0 | 0 |
| 5 | GPT-5.5 | 411 | 1,221 | 25.18% | 0 | 0 |
| 6 | GPT-6 Sol | 408 | 1,224 | 25.00% | 0 | 0 |
| 7 | GPT-5.6 Sol | 386 | 1,246 | 23.65% | 0 | 0 |
| 8 | Qwen 3.8 Flash Next | 379 | 1,253 | 23.22% | 0 | 1 |
| 9 | Gemini 3.7 Flash | 355 | 1,277 | 21.75% | 0 | 0 |
| 10 | Claude Fable 5.1 † | 353 | 1,279 | 21.63% | 668 | 82 |
| 11 | Claude Opus 4.8 | 327 | 1,305 | 20.04% | 0 | 0 |
| 12 | GPT-6 Luna | 290 | 1,342 | 17.77% | 0 | 0 |
| 13 | Claude Opus 5 † | 260 | 1,372 | 15.93% | 1,044 | 4 |
| 14 | GLM 5.3 | 241 | 1,391 | 14.77% | 0 | 0 |
| 15 | Qwen-AgentWorld-35B-A3B ‡ | 236 | 1,396 | 14.46% | 0 | 0 |
| 16 | Kimi K3 | 228 | 1,404 | 13.97% | 0 | 0 |
| 17 | Inkling | 194 | 1,438 | 11.89% | 0 | 0 |
| 18 | Claude Fable 5 † | 119 | 1,513 | 7.29% | 1,309 | 0 |
| 19 | Digital World Model (DWM) ‡ | 85 | 1,547 | 5.21% | 0 | 0 |
| 20 | Laguna S2.1 | 40 | 1,592 | 2.45% | 0 | 0 |
| | **All 20 (pooled)** | **6,423** | **26,217** | **19.68%** | **3,696** | **90** |

The pooled rate divides all passes by 20 x 1,632 and equals the mean of the
per-model rates.

Refusals are provider stops with `finish_reason: content_filter`, including
24 that carry partial text (21 from Claude Opus 5.5, one from each other
refusing model). With refusals removed from the denominator, the four refusing
models would score 44.93% (Claude Opus 5.5), 36.62% (Claude Fable 5.1), 44.22%
(Claude Opus 5), and 36.84% (Claude Fable 5). These rates depend on which items
each model chose to answer and are diagnostics only.

Reproduce this table offline with `python rescore_offline.py`.
