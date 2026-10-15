import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import harness
from deterministic_grader import grade_detail

RELEASE = Path(__file__).resolve().parents[1]


def released_rows(stem, wanted, key):
    """Rows of a released JSONL file (single or split into parts) whose key is wanted."""
    single = RELEASE / f"{stem}.jsonl"
    paths = [single] if single.is_file() else sorted((RELEASE / f"{stem}.parts").glob("*.jsonl"))
    rows = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if any(f'"{key}": "{value}"' in line or f'"{key}":"{value}"' in line for value in wanted):
                    row = json.loads(line)
                    if row.get(key) in wanted:
                        rows.append(row)
    return rows


def judgment(verdict="fail", confidence=0.9, semantic=False, contract=True):
    return json.dumps(
        {
            "semantic_correct": semantic,
            "contract_compliant": contract,
            "verdict": verdict,
            "reason_codes": ["wrong_value"],
            "confidence": confidence,
            "rationale": "The predicted value contradicts the executed result.",
        }
    )


def item():
    return {
        "item_id": "x",
        "messages": [{"role": "user", "content": "read counter"}],
        "executed_gold": "2",
        "scoring_contract": {"mode": "exact", "order_sensitive": True},
    }


class FakeClient:
    def __init__(self, values):
        self.values = iter(values)

    def complete(self, model, messages, params):
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, harness.Completion):
            return value
        return harness.Completion(value, "stop", {}, model, 1)


def evaluate(values):
    return harness.evaluate_item(
        item(),
        FakeClient(values),
        subject_model="subject",
        judge_model="judge",
        secondary_judge_model="",
        subject_params={"reasoning": {"effort": "high"}},
        judge_params={"reasoning": {"effort": "low"}},
        min_confidence=0.8,
    )


class HarnessTests(unittest.TestCase):
    def test_inline_shell_claims_ignore_alignment_padding_but_not_values(self):
        gold = "target=pool.conf kind=file lines=1 bytes=17 checksum=385"
        padded = (
            "target=pool.conf kind=file lines=        1 "
            "bytes=       17 checksum=385"
        )
        equivalent = grade_detail(padded, gold)
        self.assertTrue(equivalent.correct)
        self.assertEqual(equivalent.matched_claims, 5)
        wrong = grade_detail(
            "target=pool.conf kind=file lines=1 bytes=18 checksum=385", gold
        )
        self.assertFalse(wrong.correct)
        self.assertEqual(wrong.contradictory_claims, ("bytes",))

    def test_traceback_frame_is_not_the_error_referent(self):
        gold = "NameError: name 'p' is not defined"
        traceback = (
            "Traceback (most recent call last):\n"
            "  File \"<stdin>\", line 1, in <module>\n"
            "NameError: name 'p' is not defined"
        )
        result = grade_detail(traceback, gold)
        self.assertTrue(result.correct)
        self.assertEqual(result.pred_referent, "p")

    def test_pytest_module_error_prefers_missing_module_over_test_path(self):
        gold = "ModuleNotFoundError: No module named 'catalog.retry_backoff'"
        equivalent = (
            "ImportError while importing test module '/repo/tests/test_retry_backoff.py'.\n"
            "Original error message:\n"
            "No module named 'catalog.retry_backoff'"
        )
        wrong = equivalent.replace("catalog.retry_backoff", "ledger.retry_backoff")
        result = grade_detail(equivalent, gold)
        self.assertTrue(result.correct, result)
        self.assertEqual(result.pred_referent, "catalog.retry_backoff")
        self.assertFalse(grade_detail(wrong, gold).correct)

    def test_shell_error_prefers_path_adjacent_to_errno(self):
        gold = (
            "/work/etc/keepalived/upstream.conf\n"
            "cat: can't open '/work/etc/keepalived/upstream.conf.link': "
            "No such file or directory"
        )
        equivalent = (
            "/work/etc/keepalived/upstream.conf\n"
            "cat: /work/etc/keepalived/upstream.conf.link: No such file or directory"
        )
        wrong = equivalent.replace("upstream.conf.link", "downstream.conf.link")
        self.assertTrue(grade_detail(equivalent, gold).correct)
        self.assertFalse(grade_detail(wrong, gold).correct)

    def test_explicit_tool_response_is_graded_without_hidden_reasoning(self):
        gold = "count=2\nerror=cat: /missing: No such file or directory"
        pred = (
            "wrong analysis with count=99</think>\n<tool_response>\n"
            "count=2\nerror=cat: /missing: No such file or directory\n"
            "</tool_response>"
        )
        self.assertTrue(grade_detail(pred, gold).correct)
        self.assertFalse(grade_detail(pred.replace("count=2", "count=3"), gold).correct)

    def test_provider_exit_status_suffix_is_not_world_state(self):
        gold = "batch_rc=1\nmissing=/tmp/x"
        pred = gold + "\n\n(exit status: 1)"
        self.assertTrue(grade_detail(pred, gold).correct)

    def test_multiple_gold_errors_require_every_error_event(self):
        gold = (
            "fatal: path 'ledger/worker.py' does not exist in 'HEAD'\n"
            "fatal: path 'tests/test_worker.py' does not exist in 'HEAD'"
        )
        one_only = "cat: ledger/worker.py: No such file or directory"
        equivalent = (
            "cat: ledger/worker.py: No such file or directory\n"
            "cat: tests/test_worker.py: No such file or directory"
        )
        self.assertFalse(grade_detail(one_only, gold).correct)
        self.assertTrue(grade_detail(equivalent, gold).correct)

    def test_deterministic_contradiction_wins_after_successful_llm_audit(self):
        row = evaluate(["3", judgment()])
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["score"], 0)
        self.assertEqual(row["item"], item())

    def test_deterministic_equivalence_wins_after_successful_llm_audit(self):
        row = evaluate(["2", judgment("pass", semantic=True, contract=True)])
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["score"], 1)

    def test_non_evidence_never_becomes_a_failure(self):
        cases = [
            ([RuntimeError("provider down")], "subject_provider_error"),
            (["", judgment()], "empty_subject_response"),
            (["3", "not json"], "no_successful_llm_audit"),
            (["3", judgment(confidence=0.5)], "no_successful_llm_audit"),
            (["3", judgment("uncertain")], "no_successful_llm_audit"),
        ]
        for values, reason in cases:
            with self.subTest(reason=reason):
                row = evaluate(values)
                self.assertEqual(row["status"], "unresolved")
                self.assertIsNone(row["score"])
                self.assertEqual(row["unresolved_reason"], reason)

    def test_natural_language_refusal_never_becomes_a_failure(self):
        row = evaluate(["I'm sorry, but I cannot help with that."])
        self.assertEqual(row["status"], "unresolved")
        self.assertIsNone(row["score"])
        self.assertEqual(row["unresolved_reason"], "subject_refusal")

    def test_structured_provider_refusal_never_becomes_a_failure(self):
        refused = harness.Completion("", "stop", {}, "subject", 1, "policy")
        row = evaluate([refused])
        self.assertEqual(row["status"], "unresolved")
        self.assertIsNone(row["score"])
        self.assertEqual(row["unresolved_reason"], "subject_refusal")

    def test_context_overflow_never_becomes_a_failure(self):
        completion = harness.Completion("partial", "context_overflow", {}, "subject", 1)
        row = evaluate([completion])
        self.assertEqual(row["status"], "unresolved")
        self.assertEqual(row["unresolved_reason"], "subject_truncated")

    def test_parser_rejects_inconsistent_or_duplicate_fields(self):
        inconsistent = harness.parse_judgment(
            judgment("pass", semantic=False, contract=True), 0.8
        )
        self.assertEqual(inconsistent["effective_verdict"], "uncertain")
        duplicate = judgment()[:-1] + ', "confidence": 0.99}'
        with self.assertRaisesRegex(ValueError, "duplicate"):
            harness.parse_judgment(duplicate, 0.8)

    def test_format_is_reported_separately_from_semantic_correctness(self):
        row = evaluate(["2", judgment("pass", semantic=True, contract=False)])
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["score"], 1)
        self.assertEqual(row["format_status"], "fail")

    def test_secondary_judge_resolves_uncertain_primary(self):
        row = harness.evaluate_item(
            item(),
            FakeClient([
                "an answer that needs semantic adjudication",
                judgment("uncertain", confidence=0.9),
                judgment("pass", semantic=True, contract=True),
            ]),
            subject_model="subject",
            judge_model="primary",
            secondary_judge_model="secondary",
            subject_params={"reasoning": {"effort": "high"}},
            judge_params={"reasoning": {"effort": "low"}},
            min_confidence=0.8,
        )
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["resolution_rule"], "secondary_semantic_adjudication")

    def test_loader_requires_exact_published_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "items.jsonl"
            path.write_text(json.dumps(item()) + "\n", encoding="utf-8")
            self.assertEqual(
                harness.load_items(path)[0]["messages"][0]["content"],
                "read counter",
            )
            bad = item()
            bad.pop("messages")
            path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "messages"):
                harness.load_items(path)

    def test_loader_normalizes_four_field_release_rows(self):
        public = {
            "example_id": "public-x",
            "messages": [{"role": "user", "content": "read counter"}],
            "target": "2",
            "metadata": {
                "domain": "code",
                "scoring": {"mode": "exact", "order_sensitive": True},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "eval.jsonl"
            path.write_text(json.dumps(public) + "\n", encoding="utf-8")
            loaded = harness.load_items(path)[0]
        self.assertEqual(loaded["item_id"], "public-x")
        self.assertEqual(loaded["executed_gold"], "2")
        self.assertEqual(loaded["scoring_contract"]["mode"], "exact")

    def test_resume_survives_torn_and_unicode_separator_ledger_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.partial.jsonl"
            good = {"item_id": "a", "status": "pass", "note": "line\u2028break"}
            path.write_text(
                json.dumps(good, ensure_ascii=False) + "\n"
                + "null\n"
                + '{"item_id": "b", "sub',
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                rows = harness.read_partial(path)
            self.assertEqual(rows, {"a": good})

    def test_prompt_is_frozen_and_contains_only_public_evidence(self):
        messages = harness.judge_messages(item(), "3")
        self.assertEqual(harness.JUDGE_PROMPT_VERSION, "wm-response-judge/4")
        payload = json.loads(messages[1]["content"])
        self.assertEqual(
            payload,
            {
                "prompt_version": "wm-response-judge/4",
                "model_visible_messages": item()["messages"],
                "executed_gold": "2",
                "scoring_contract": item()["scoring_contract"],
                "subject": {"response": "3"},
            },
        )

    def test_judge_prompt_uses_the_evaluation_serialization(self):
        released = {
            "item_id": "x",
            "messages": [{"content": "read counter", "role": "user"}],
            "executed_gold": "2",
            "scoring_contract": {
                "adjudication_policy": "judge_on_abstain",
                "mode": "exact",
                "order_sensitive": True,
            },
        }
        messages = harness.judge_messages(released, "3")
        self.assertEqual(
            messages[1]["content"],
            '{"prompt_version": "wm-response-judge/4", "model_visible_messages": '
            '[{"role": "user", "content": "read counter"}], "executed_gold": "2", '
            '"scoring_contract": {"mode": "exact", "order_sensitive": true, '
            '"adjudication_policy": "judge_on_abstain"}, "subject": {"response": "3"}}',
        )
        self.assertEqual(
            harness.judge_prompt_sha256(messages),
            hashlib.sha256(
                json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        )

    def test_loader_attaches_judge_contracts_only_to_items_without_one(self):
        contract = {"mode": "structured", "order_sensitive": False}
        rows = [
            {"example_id": "empty", "messages": [{"role": "user", "content": "a"}],
             "target": "1", "metadata": {"scoring": {}}},
            {"example_id": "own", "messages": [{"role": "user", "content": "b"}],
             "target": "2", "metadata": {"scoring": {"mode": "exact"}}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "eval.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            self.assertNotIn("judge_scoring_contract", harness.load_items(path)[0])
            (Path(directory) / harness.JUDGE_CONTRACTS_FILE).write_text(
                json.dumps({"example_id": "empty", "scoring_contract": contract}) + "\n"
                + json.dumps({"example_id": "own", "scoring_contract": contract}) + "\n",
                encoding="utf-8",
            )
            empty, own = harness.load_items(path)
            with self.assertRaises(FileNotFoundError):
                harness.load_items(path, Path(directory) / "missing.jsonl")
        self.assertEqual(empty["scoring_contract"], {})
        self.assertEqual(empty["judge_scoring_contract"], contract)
        self.assertNotIn("judge_scoring_contract", own)
        payload = json.loads(harness.judge_messages(empty, "1")[1]["content"])
        self.assertEqual(payload["scoring_contract"], contract)

    @unittest.skipUnless(RELEASE.joinpath("data").is_dir(), "released data not present")
    def test_released_judge_rows_bind_the_rendered_prompt(self):
        # One item with and one without a released scoring contract.
        wanted = {
            "math-dual_path_read-h3-r1-dual_path_read-twin",
            "ar2g-game-quota-recovery-h10-r40009-n0037-quota_enforcement_probe-injected",
        }
        items = {
            row["example_id"]: row
            for row in released_rows("data/eval", wanted, "example_id")
        }
        contracts = harness.load_judge_contracts(
            RELEASE / "data" / harness.JUDGE_CONTRACTS_FILE
        )
        predictions = {
            row["item_id"]: row["prediction"]
            for row in released_rows("runs/subject_gpt6astra/results", wanted, "item_id")
        }
        judged = released_rows(
            "runs/final_judge_gpt6astra/openai__gpt-6-astra/judgments", wanted, "item_id"
        )
        self.assertEqual({row["item_id"] for row in judged}, wanted)
        for row in judged:
            source = items[row["item_id"]]
            scoring = source["metadata"]["scoring"]
            rendered = {
                "messages": source["messages"],
                "executed_gold": source["target"],
                "scoring_contract": scoring,
            }
            if not scoring:
                rendered["judge_scoring_contract"] = contracts[row["item_id"]]
            messages = harness.judge_messages(rendered, predictions[row["item_id"]])
            self.assertEqual(harness.judge_prompt_sha256(messages), row["prompt_sha256"])



if __name__ == "__main__":
    unittest.main()
