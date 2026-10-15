# Paper files

Results (20 models):

- `LEADERBOARD.md`, `FINAL_BINARY_LEADERBOARD.json`: the binary leaderboard
  of all 20 models, with refusals and other non-responses.
- `FAILURE_ANATOMY.md`, `FAILURE_ANATOMY.json`: the 20-model failure anatomy,
  per-model profiles, any-label and primary-skill slices, item difficulty, and
  pairwise complementarity. Rebuilt by `analyze_failure_anatomy.py`.

Audit:

- `llm_quality_audit.json`, `llm_quality_audit_schema.json`: the two-phase
  LLM quality audit of every item's gold next state (records in
  `runs/llm_quality_audit/`).
