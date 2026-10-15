"""Deterministic, standard-library-only grader for GlobeBench predictions.

It compares a prediction with the execution-derived gold and accepts
differences of notation, never of state. Two examples:

- Database golds are ``json.dumps(rows, sort_keys=True)``. A model that emits
  the same rows with a different key order, single quotes, or a trailing
  comma is right about the world and only differs in formatting.
- Alpine busybox says ``cat: can't open '/p': No such file or directory``
  while GNU coreutils says ``cat: /p: No such file or directory``. Same errno,
  same referent, same state.

What this module does NOT do: accept a prediction that names a *different*
referent, a different error class, or a different value. Every leniency here
is a leniency about *notation*, never about *state*. The one deliberate
exception is spelled out on ``EMPTY_SYNONYMS``.

Grading ladder (first rung that decides, wins) -- ``GradeResult.mode`` names
the rung so the runner can report WHY:

    exact        normalized texts identical
    empty        gold is empty output; pred says so in words
    json         both parse as JSON-ish; canonical structures compared
    json_order   same rows, wrong order (only when order_sensitive=True)
    numeric      both are bare numbers (ints exact, floats rel 1e-9)
    error_prose  both read as errors, identical up to case/quote style
    error_class  both map to the same equivalence class + same referent
    error_referent   same class, DIFFERENT referent  -> WRONG
    error_class_mismatch / error_missing / error_spurious -> WRONG
    mismatch     nothing matched -> WRONG

Order sensitivity: ``order_sensitive=True`` is the default and is strict.
Row lists compare order-insensitively only when the caller says the gold
query imposed no order (``order_sensitive_for_sql`` / ``_for_item`` compute
that from the action text: no ORDER BY -> the row order is arbitrary and
must not be graded).
"""

from __future__ import annotations


#: Grader identity. It names the equivalence table and grading modes; the
#: runner records it on every result row.
GRADER_VERSION = "wm-grader-1.5"


def grader_fingerprint() -> str:
    """Version plus a digest of the complete scoring implementation.

    Parsing, referent extraction, structured comparison, and abstention policy
    are as consequential as the equivalence table, so the digest covers the
    whole module.
    """
    import hashlib as _h
    import inspect as _inspect
    import sys as _sys
    payload = _inspect.getsource(_sys.modules[__name__]).encode("utf-8")
    return f"{GRADER_VERSION}+{_h.blake2b(payload, digest_size=6).hexdigest()}"


import ast
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

# ``grade_detail`` grades predictions; ``score_probe`` and the change-set
# helpers at the end of this module label probe items. These sentinel classes
# keep the module importable on its own.
class ChangeTuple:  # pragma: no cover
    pass


class ItemRecord:  # pragma: no cover
    pass

__all__ = [
    "GradeResult", "grade", "grade_detail", "make_grader",
    "EQUIVALENCE_CLASSES", "CLASS_ALIASES", "EMPTY_SYNONYMS",
    "classify_error", "ErrorMatch", "classify_error_detail",
    "extract_referent", "error_family", "provider_neutral_family",
    "canonical_class",
    "matches_error_class",
    "normalize_text", "parse_structured", "struct_eq",
    "ContentClaims", "parse_content_claims", "CompositeError",
    "parse_composite_error",
    "order_sensitive_for_sql", "order_sensitive_for_item",
    "infer_scoring_mode", "stamp_scoring_spec",
    "ChangeSetScore", "grade_change_set", "grade_change_set_detail",
    "frame_violations", "ProbeScore", "score_probe",
    "REL_TOL",
]

# Relative tolerance for float comparison. Ints never get a tolerance.
REL_TOL = 1e-9


# --------------------------------------------------------------- text prep
_WS = re.compile(r"\s+")
_FENCE = re.compile(r"\A```[A-Za-z0-9_+.\-]*[ \t]*\r?\n?(.*?)\r?\n?```\Z", re.S)
_TOOL_RESPONSE = re.compile(
    r"<tool_response>\s*(.*?)\s*</tool_response>\s*\Z", re.S | re.I
)
_EXIT_STATUS_SUFFIX = re.compile(r"\s*\(exit status:\s*\d+\)\s*\Z", re.I)
_CONTRACTIONS = re.compile(
    r"\b(can't|don't|doesn't|didn't|won't|isn't|aren't|couldn't|wasn't)\b",
    re.I,
)
_CONTRACTION_MAP = {
    "can't": "cannot", "don't": "do not", "doesn't": "does not",
    "didn't": "did not", "won't": "will not", "isn't": "is not",
    "aren't": "are not", "couldn't": "could not", "wasn't": "was not",
}


def normalize_text(s: str) -> str:
    """Canonical form for text comparison: strip + collapse whitespace runs.

    Deliberately CASE-PRESERVING: identifiers, paths and values are cased
    data. Case-insensitivity is applied only to error prose, further down.
    """
    return _WS.sub(" ", s).strip()


def _strip_fence(s: str) -> str:
    m = _FENCE.match(s.strip())
    return m.group(1) if m else s


def _strip_wrapping_quotes(s: str) -> str:
    t = s.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"`" and t[0] not in t[1:-1]:
        return t[1:-1]
    return s


def _prep_pred(pred: str, gold: str) -> tuple[str, list[str]]:
    """Undo presentation wrappers a model adds that the executor never emits.

    Only ever applied when the GOLD does not itself contain the wrapper, so
    a gold that legitimately contains backticks or quotes is never mangled.
    """
    notes: list[str] = []
    out = pred
    if "<tool_response>" not in gold.casefold():
        match = _TOOL_RESPONSE.search(out)
        if match:
            out = match.group(1)
            notes.append("extracted explicit tool_response payload")
    if "(exit status:" not in gold.casefold():
        stripped = _EXIT_STATUS_SUFFIX.sub("", out)
        if stripped != out:
            out = stripped
            notes.append("stripped provider exit-status suffix")
    if "```" not in gold and "```" in out:
        stripped = _strip_fence(out)
        if stripped != out:
            out = stripped
            notes.append("stripped code fence")
    gq = gold.strip()
    if not (gq[:1] in "'\"`" and gq[-1:] in "'\"`"):
        stripped = _strip_wrapping_quotes(out)
        if stripped != out:
            out = stripped
            notes.append("stripped wrapping quotes")
    return out, notes


_ANSWER_ENVELOPE_KEYS = frozenset({
    "answer", "error", "output", "response", "result", "value",
})


def _unwrap_singleton_answer(text: str) -> tuple[str, str]:
    """Unwrap a model-added one-field answer envelope.

    ``{"error": "FileNotFoundError: target 'x' not found"}`` and the plain
    executor error carry the same claim.  This is deliberately limited to a
    single recognized key whose value is a string: metadata, multiple claims,
    and arbitrary structured payloads remain strict.
    """
    ok, value = parse_structured(text)
    if not ok or not isinstance(value, dict) or len(value) != 1:
        return text, ""
    key, inner = next(iter(value.items()))
    if not isinstance(key, str) or key.casefold() not in _ANSWER_ENVELOPE_KEYS:
        return text, ""
    if not isinstance(inner, str):
        return text, ""
    return inner, f"unwrapped singleton {key!r} answer envelope"


def _expand_contractions(s: str) -> str:
    """busybox writes ``can't open``; the apostrophe otherwise eats the
    quote-pairing used for referent extraction. Classification does NOT use
    this (the phrase table lists both spellings verbatim)."""
    return _CONTRACTIONS.sub(
        lambda m: _CONTRACTION_MAP[m.group(0).lower()], s
    )


# gold text is empty for a successful silent mutation ("" is the whole
# observation). A model has no way to type "nothing", so these stand-ins for
# "the command printed nothing" are accepted -- and ONLY when the gold is
# genuinely empty, so none of them can ever mask a real value.
EMPTY_SYNONYMS = frozenset({
    "", "()", "(empty)", "empty", "<empty>", "(no output)", "no output",
    "(none)", "none", "null", "nil", "nothing", "(nothing)", "n/a",
    "''", '""', "(blank)", "blank", "(no stdout)", "no stdout",
})


# ------------------------------------------------------------ JSON parsing
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _py_bridge(s: str) -> str:
    """Rewrite JSON-isms into Python literals *outside string literals*:
    ``true/false/null`` -> ``True/False/None`` and trailing commas dropped,
    so ``ast.literal_eval`` can take mixed JSON/Python output. Quote-state
    aware; never touches text inside quotes."""
    out: list[str] = []
    i, n, quote = 0, len(s), ""
    while i < n:
        ch = s[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(s[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
            continue
        m = _WORD.match(s, i)
        if m:
            w = m.group(0)
            out.append({
                "true": "True", "false": "False", "null": "None",
            }.get(w.lower(), w))
            i = m.end()
            continue
        if ch == ",":
            j = i + 1
            while j < n and s[j].isspace():
                j += 1
            if j < n and s[j] in "]}":
                i += 1          # trailing comma before a closer: drop it
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _jsonable(v: Any) -> Any:
    """Coerce an ast.literal_eval result into the JSON value space, or raise
    ValueError if it holds something JSON has no notion of."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return [_jsonable(x) for x in sorted(v, key=repr)]
    if isinstance(v, dict):
        out: dict[str, Any] = {}
        for k, val in v.items():
            if isinstance(k, str):
                key = k
            elif isinstance(k, (int, float, bool)) or k is None:
                key = json.dumps(k)
            else:
                raise ValueError(f"non-JSON key {k!r}")
            out[key] = _jsonable(val)
        return out
    raise ValueError(f"non-JSON value {type(v).__name__}")


def parse_structured(text: str) -> tuple[bool, Any]:
    """Lenient structural parse. Returns (parsed_ok, value).

    Three passes, strictest first: json -> ast.literal_eval (single quotes,
    Python True/None, tuples, trailing commas) -> a quote-state-aware bridge
    that maps bare true/false/null to Python literals and drops trailing
    commas, then ast again. Never evaluates code (literal_eval only).
    """
    t = text.strip()
    if not t:
        return False, None
    try:
        return True, json.loads(t)
    except Exception:
        pass
    for candidate in (t, _py_bridge(t)):
        try:
            return True, _jsonable(ast.literal_eval(candidate))
        except Exception:
            continue
    return False, None


def _is_container(v: Any) -> bool:
    return isinstance(v, (list, dict))


def _num(v: Any) -> float | None:
    """Numeric view of a value; bools are NOT numbers here (True != 1)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


_NULL_WORDS = frozenset({"null", "none", "nil"})


def struct_eq(a: Any, b: Any, order_sensitive: bool = True) -> bool:
    """Canonical structural equality.

    - dicts: key sets equal (keys are identifiers -> case-sensitive), values
      compared recursively. Key ORDER is never significant.
    - lists: elementwise when order_sensitive, else multiset (each gold
      element must match a distinct pred element).
    - numbers: int vs int is exact; anything involving a float uses
      rel_tol=REL_TOL. A number quoted as a string ("450" vs 450) compares
      numerically -- quoting is notation, not state.
    - bools are distinct from 0/1; None matches the null spellings.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        if isinstance(a, bool) and isinstance(b, bool):
            return a is b
        # allow a bool spelled as its json/python word
        other, flag = (b, a) if isinstance(a, bool) else (a, b)
        if isinstance(other, str):
            return other.strip().lower() == ("true" if flag else "false")
        return False
    if a is None or b is None:
        if a is None and b is None:
            return True
        other = b if a is None else a
        return isinstance(other, str) and other.strip().lower() in _NULL_WORDS
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(struct_eq(a[k], b[k], order_sensitive) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        if order_sensitive:
            return all(struct_eq(x, y, True) for x, y in zip(a, b))
        # Greedy multiset match. Quadratic, but only reachable when the two
        # lists are the SAME length, and one of them is always our (small)
        # execution-derived gold - a model dumping 100k rows exits on the
        # length check above.
        used = [False] * len(b)
        for x in a:
            for j, y in enumerate(b):
                if not used[j] and struct_eq(x, y, False):
                    used[j] = True
                    break
            else:
                return False
        return True
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return False
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        if isinstance(a, int) and isinstance(b, int):
            return a == b
        return math.isclose(na, nb, rel_tol=REL_TOL, abs_tol=0.0)
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return a == b


@dataclass(frozen=True)
class ContentClaims:
    """A fully parsed sequence of conservative text claims.

    This is intentionally not free-form information extraction.  A text is
    claim-shaped only when every nonblank line is either ``key=value`` or an
    audit transition ``key: before -> after``.  Partial parses are rejected.
    """
    claims: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class CompositeError:
    """A generated audit snapshot followed by its terminal failure reason."""

    audit: dict[str, Any]
    reason: str


_LEADING_ERROR_LABEL = re.compile(
    r"\A\s*(?:native\s+)?(?:[A-Za-z_][\w.]*(?:error|exception|fault))\s*:\s*",
    re.I,
)


def _balanced_mapping(text: str) -> tuple[int, int, str] | None:
    """Return the first quote-aware balanced ``{...}`` span."""
    start = text.find("{")
    if start < 0:
        return None
    depth, quote, escaped = 0, "", False
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1, text[start:i + 1]
    return None


def _clean_error_reason(text: str) -> str:
    out = text.strip(" \t\r\n;:,=")
    out = re.sub(r"\A(?:redirect\s+)?audit\s*[:=]?\s*", "", out,
                 flags=re.I)
    out = _LEADING_ERROR_LABEL.sub("", out)
    return _prose_key(out)


def parse_composite_error(text: str) -> CompositeError | None:
    """Parse ``audit {structured state}; Error: reason`` without fuzziness.

    The dialogue generator emits this contract in several harmless surface
    forms (Python/JSON mappings, ``audit=``/``redirect audit``, and an outer
    ``{"audit": ..., "error": ...}`` envelope).  Both the complete audit
    mapping and the terminal reason remain mandatory.
    """
    ok, whole = parse_structured(text)
    if ok and isinstance(whole, dict) and set(whole) == {"audit", "error"}:
        audit, reason = whole["audit"], whole["error"]
        if isinstance(audit, dict) and isinstance(reason, str):
            cleaned = _clean_error_reason(reason)
            return CompositeError(audit, cleaned) if cleaned else None

    span = _balanced_mapping(text)
    if span is None:
        return None
    start, end, mapping_text = span
    if not (_EXC_NAME.search(text[:start]) or _EXC_NAME.search(text[end:])):
        return None
    ok, audit = parse_structured(mapping_text)
    if not ok or not isinstance(audit, dict):
        return None
    if set(audit) == {"audit", "error"}:
        nested, nested_reason = audit["audit"], audit["error"]
        if isinstance(nested, dict) and isinstance(nested_reason, str):
            cleaned = _clean_error_reason(nested_reason)
            return CompositeError(nested, cleaned) if cleaned else None
    # The semantic failure is emitted after the audit. Prefix labels describe
    # the container, not the failure itself.
    suffix = text[end:].strip()
    if not suffix:
        return None
    cleaned = _clean_error_reason(suffix)
    return CompositeError(audit, cleaned) if cleaned else None


_CLAIM_ASSIGN = re.compile(r"\A([A-Za-z_][\w.\-/\[\]]*)\s*=\s*(.+)\Z")
_CLAIM_AUDIT = re.compile(
    r"\A([A-Za-z_][\w.\-/\[\]]*)\s*:\s*(.+?)\s*->\s*(.+)\Z"
)
_INLINE_CLAIM = re.compile(
    r"(?:\A|\s)([A-Za-z_][\w.\-/\[\]]*)\s*=\s*(.*?)"
    r"(?=\s+[A-Za-z_][\w.\-/\[\]]*\s*=|\Z)"
)


def _claim_value(text: str) -> Any:
    ok, value = parse_structured(text)
    return value if ok else normalize_text(text)


def _inline_claims(line: str) -> list[tuple[str, Any]] | None:
    """Parse a complete one-line ``key=value key=value`` status record.

    Shell tools right-align numeric fields, so command substitution can emit
    ``lines=        1`` while an equivalent model answer emits ``lines=1``.
    The parse is all-or-nothing and requires at least two assignments.
    """
    matches = list(_INLINE_CLAIM.finditer(line))
    if len(matches) < 2 or matches[0].start() != 0 or matches[-1].end() != len(line):
        return None
    out: list[tuple[str, Any]] = []
    for match in matches:
        value = match.group(2).strip()
        if not value:
            return None
        out.append((match.group(1), _claim_value(value)))
    return out


def parse_content_claims(text: str) -> ContentClaims | None:
    """Parse an all-or-nothing key/value or audit-line claim document."""
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines:
        return None
    out: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for line in lines:
        inline = _inline_claims(line)
        if inline is not None:
            if any(key in seen for key, _ in inline):
                return None
            for key, value in inline:
                seen.add(key)
                out.append((key, value))
            continue
        m = _CLAIM_ASSIGN.match(line)
        if m:
            key, value = m.group(1), _claim_value(m.group(2))
        else:
            m = _CLAIM_AUDIT.match(line)
            if not m:
                return None
            key = m.group(1)
            value = {"before": _claim_value(m.group(2)),
                     "after": _claim_value(m.group(3))}
        # Duplicate keys make ordering/overwrite semantics ambiguous, so the
        # conservative parser declines the whole document.
        if key in seen:
            return None
        seen.add(key)
        out.append((key, value))
    return ContentClaims(tuple(out))


def _claim_differences(
    gold: dict[str, Any], pred: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], int]:
    missing = tuple(sorted(set(gold) - set(pred)))
    extra = tuple(sorted(set(pred) - set(gold)))
    contradictory = tuple(sorted(
        key for key in set(gold) & set(pred)
        if not struct_eq(gold[key], pred[key], True)
    ))
    matched = sum(
        struct_eq(gold[key], pred[key], True)
        for key in set(gold) & set(pred)
    )
    return missing, extra, contradictory, matched


def _flatten_structured(value: Any, path: str = "$") -> dict[str, Any]:
    """Leaf claims for diagnostics; list indices preserve state semantics."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value):
            out.update(_flatten_structured(value[key], f"{path}.{key}"))
        return out
    if isinstance(value, list):
        out = {}
        for i, child in enumerate(value):
            out.update(_flatten_structured(child, f"{path}[{i}]"))
        return out
    return {path: value}


# ------------------------------------------------- error equivalence table
#
# EQUIVALENCE_CLASSES maps a canonical error class to the phrasings that mean
# it, across the userlands/drivers/languages our executors span (alpine
# busybox vs GNU coreutils; sqlite vs postgres; python exception names vs
# errno names; HTTP codes vs reason phrases). This table defines how error
# wording is graded.
#
# Entries are lowercase substrings, except:
#   - "re:<pattern>" entries are regexes (matched against the same
#     lowercased, whitespace-collapsed text),
#   - pure digit entries are matched word-bounded (so "404" never fires on
#     "id 4041").
# Classification picks the LONGEST matching phrase across the whole table,
# which is what makes the specific class win over the generic one
# ("permission denied" beats "can't open"; "command not found" beats
# "not found"; "foreign key constraint failed" beats "integrityerror").
# Dotted names are hierarchical: family = text before the first dot.
EQUIVALENCE_CLASSES: dict[str, tuple[str, ...]] = {
    # ---- POSIX filesystem (busybox / GNU coreutils / python) -------------
    "ENOENT": (
        "no such file or directory", "no such file", "cannot open",
        "can't open", "cannot access", "can't access", "cannot remove",
        "can't remove", "cannot stat", "can't stat", "does not exist",
        "filenotfounderror", "enoent",
    ),
    "EACCES": (
        "permission denied", "permissionerror", "eacces",
        # Odoo's XML-RPC access faults carry a numeric code and no exception
        # name; these entries classify them.
        "access to", "not allowed to access", "accesserror",
        "top-secret records",
        # TextWorld locks: refusal by policy rather than by absence.
        "is welded shut", "doesn't seem to fit the lock",
    ),
    "EPERM": (
        "operation not permitted", "eperm",
    ),
    "EEXIST": (
        "file exists", "already exists", "fileexistserror", "eexist",
    ),
    "EISDIR": (
        "is a directory", "isadirectoryerror", "eisdir",
    ),
    "ENOTDIR": (
        "not a directory", "notadirectoryerror", "enotdir",
    ),
    "ENOTEMPTY": (
        "directory not empty", "enotempty",
    ),
    "ENOSPC": (
        "no space left on device", "enospc",
    ),
    "EDQUOT": (
        "disk quota exceeded", "quota exceeded", "edquot",
        # tau2's retail backend reports a depleted payment instrument as a
        # value error.  The exception name is incidental; semantically this
        # is the same resource-exhaustion event whether the model reproduces
        # the full backend wording or the concise reason.
        "insufficient gift card balance",
    ),
    "COMMAND_NOT_FOUND": (
        "command not found", ": not found", "executable file not found",
        "no such command",
    ),
    # ---- SQL: sqlite3 + postgres wording of the same constraint ----------
    # Two classes that no filesystem/SQL vocabulary covers but that three
    # domains produce often.
    #
    # STATE_REFUSED: the operation is legal in general and refused HERE
    # because of the record's current state. Odoo ("you can not delete a sent
    # quotation or a confirmed sales order"), TicketAPI ("Ticket with ID 41
    # is already closed."), and TextWorld ("That's already closed.") all say
    # the same thing in three vocabularies.
    "STATE_REFUSED": (
        "you can not delete a sent quotation", "confirmed sales order",
        "is already closed", "is already open", "already been cancelled",
        "already cancelled", "that's already open", "that's already closed",
        # TicketAPI resolves as well as closes; both refusals are STATE_REFUSED.
        "is already resolved",
        "cannot be deleted in this state", "invalid state transition",
        "not in a state that allows",
        # TextWorld preconditions: the action is legal once the world is in
        # the right state, which is exactly what STATE_REFUSED means.
        "you have to open the", "you need to take the",
        "that's fixed in place", "can't see inside, since",
        "you already have that", "that's plainly inedible",
    ),
    # VALUE_INVALID: the field exists, the value does not belong to it -
    # distinct from a missing referent (ENOENT) and from a constraint
    # violation the store rejects (IntegrityError.CHECK).
    "VALUE_INVALID": (
        "wrong value for", "invalid value for", "invalid fields for update",
        "is not a valid", "invalid field", "not a valid selection",
    ),
    # Python exception surfaces raised by the math and code executors
    # (NameError, ZeroDivisionError, TypeError, ModuleNotFoundError).
    "PY.NAME_ERROR": (
        "nameerror", "is not defined",
    ),
    "PY.MODULE_NOT_FOUND": (
        "modulenotfounderror", "no module named", "importerror",
        "cannot import name",
    ),
    "PY.TYPE_ERROR": (
        "typeerror", "unsupported operand", "is not subscriptable",
        "is not callable", "takes no arguments",
    ),
    "PY.ATTRIBUTE_ERROR": (
        "attributeerror", "has no attribute",
    ),
    "PY.ZERO_DIVISION": (
        "zerodivisionerror", "division by zero", "modulo by zero",
    ),
    "PY.INDEX_ERROR": (
        "indexerror", "index out of range", "keyerror",
    ),
    "PY.JSON_DECODE": (
        "jsondecodeerror", "expecting ',' delimiter", "expecting value",
        "expecting property name",
    ),
    "IntegrityError.FOREIGN_KEY": (
        "foreign key constraint failed", "violates foreign key constraint",
        "foreign key constraint fails", "foreign key violation",
        # Odoo phrases a blocked unlink in prose, naming the constraint at the
        # end rather than raising a named exception.
        "another model requires the record being deleted",
    ),
    "IntegrityError.UNIQUE": (
        "unique constraint failed", "violates unique constraint",
        "duplicate key value", "duplicate entry",
    ),
    "IntegrityError.NOT_NULL": (
        "not null constraint failed", "violates not-null constraint",
        "null value in column", "cannot be null",
    ),
    "IntegrityError.CHECK": (
        "check constraint failed", "violates check constraint",
    ),
    "IntegrityError": (
        "integrityerror", "integrity error", "constraint failed",
        "constraint violation",
    ),
    "OperationalError.NO_SUCH_TABLE": (
        "no such table", "undefined table", r"re:relation \S+ does not exist",
    ),
    "OperationalError.NO_SUCH_COLUMN": (
        "no such column", "undefined column", "unknown column",
        "has no column named",
    ),
    "OperationalError.SYNTAX": (
        "syntax error", "programmingerror: near",
    ),
    "OperationalError.LOCKED": (
        "database is locked", "database table is locked",
    ),
    "OperationalError": (
        "operationalerror",
    ),
    # ---- HTTP: code and reason phrase are the same statement -------------
    "HTTP.400": ("400", "bad request"),
    "HTTP.401": (
        "401", "unauthorized", "authentication required",
        "invalid credentials", "missing authentication",
        # BFCL's TicketAPI spells the same refusal in prose: "User not
        # authenticated. Please log in to create a ticket." These phrases map it to
        # HTTP.401.
        "not authenticated", "please log in",
    ),
    "HTTP.403": ("403", "forbidden", "access denied"),
    "HTTP.404": ("404", "not found", "resource not found", "unknown endpoint"),
    "HTTP.409": ("409", "conflict"),
    "HTTP.422": ("422", "unprocessable"),
    "HTTP.429": ("429", "too many requests", "rate limit"),
    "HTTP.500": ("500", "internal server error"),
    "HTTP.503": ("503", "service unavailable"),
    "GAME.LORE_DENIED": ("lore ward denies",),
    "GAME.QUOTA_EXCEEDED": ("crafting quota exceeded",),
    "GAME.NO_SUCH_THING": ("can't see any such thing",),
    "GAME.NO_EXIT": ("you can't go that way",),
    "GAME.NO_SUCH_ENTITY": ("no campaign entity named",),
}

# gold.error_class values declared by the items, mapped onto canonical table
# names.
CLASS_ALIASES: dict[str, str] = {
    "400": "HTTP.400", "401": "HTTP.401", "403": "HTTP.403",
    "404": "HTTP.404", "409": "HTTP.409", "422": "HTTP.422",
    "429": "HTTP.429", "500": "HTTP.500", "503": "HTTP.503",
    "FileNotFoundError": "ENOENT", "PermissionError": "EACCES",
    "FileExistsError": "EEXIST", "IsADirectoryError": "EISDIR",
    "NotADirectoryError": "ENOTDIR",
}

_DIGITS = re.compile(r"\A\d+\Z")
# (class, plain_phrase | None, compiled_regex | None)
_COMPILED: list[tuple[str, str | None, re.Pattern | None]] = []
for _cls, _phrases in EQUIVALENCE_CLASSES.items():
    for _p in _phrases:
        if _p.startswith("re:"):
            _COMPILED.append((_cls, None, re.compile(_p[3:])))
        elif _DIGITS.match(_p):
            # A bare 429/500 embedded in an otherwise ordinary state dump is
            # a value, not an HTTP failure.  Numeric status codes count only
            # when they are the whole output or have an explicit status/error
            # marker.  Reason phrases ("not found", "internal server error")
            # are still matched by their separate table entries.
            _COMPILED.append((_cls, None, re.compile(
                rf"(?:\A\s*{_p}\s*\Z|"
                rf"\bhttp(?:\s+status)?\s*[:=#-]?\s*{_p}\b|"
                rf"\bstatus(?:[\s_]+code)?\s*[:=#-]?\s*{_p}\b|"
                rf"\berror[\s_]+code\s*[:=#-]?\s*{_p}\b)"
            )))
        else:
            _COMPILED.append((_cls, _p, None))


def error_family(class_name: str) -> str:
    """``IntegrityError.UNIQUE`` -> ``IntegrityError``."""
    return class_name.split(".", 1)[0]


def provider_neutral_family(class_name: str) -> str:
    """Broad semantic family, independent of provider surface vocabulary.

    These are deliberately coarser than :func:`error_family`: for example,
    POSIX ``ENOENT``, HTTP 404, Python module-not-found and a game's missing
    entity all describe a missing referent.  This level is diagnostic partial
    credit only unless a caller explicitly configures it as sufficient.
    """
    c = canonical_class(class_name)
    if c in {"ENOENT", "PY.MODULE_NOT_FOUND", "HTTP.404",
             "OperationalError.NO_SUCH_TABLE",
             "OperationalError.NO_SUCH_COLUMN", "GAME.NO_SUCH_THING",
             "GAME.NO_SUCH_ENTITY", "GAME.NO_EXIT"}:
        return "missing"
    if c in {"EACCES", "EPERM", "HTTP.401", "HTTP.403",
             "GAME.LORE_DENIED"}:
        return "permission"
    if c in {"EEXIST", "HTTP.409"}:
        return "conflict"
    if c in {"ENOSPC", "EDQUOT", "HTTP.429", "GAME.QUOTA_EXCEEDED"}:
        return "quota"
    if c in {"STATE_REFUSED", "OperationalError.LOCKED"}:
        return "state"
    if c.startswith("IntegrityError"):
        return "constraint"
    if c in {"VALUE_INVALID", "HTTP.400", "HTTP.422", "PY.TYPE_ERROR",
             "PY.NAME_ERROR", "PY.ATTRIBUTE_ERROR", "PY.INDEX_ERROR",
             "PY.JSON_DECODE", "OperationalError.SYNTAX"}:
        return "invalid"
    if c in {"HTTP.500", "HTTP.503", "OperationalError"}:
        return "availability"
    if c in {"EISDIR", "ENOTDIR", "ENOTEMPTY"}:
        return "filesystem_shape"
    if c == "PY.ZERO_DIVISION":
        return "arithmetic"
    if c == "COMMAND_NOT_FOUND":
        return "missing_command"
    return error_family(c).casefold() if c else ""


def canonical_class(name: str) -> str:
    """Map a declared ``gold.error_class`` onto a table class name."""
    if name in EQUIVALENCE_CLASSES:
        return name
    if name in CLASS_ALIASES:
        return CLASS_ALIASES[name]
    return name


def _err_key(text: str) -> str:
    return normalize_text(text).casefold()


def classify_error(text: str) -> str:
    """Canonical error class for a text, or "" if it does not read as a
    known error. Longest matching phrase wins; ties break on table order,
    so the result is deterministic."""
    return classify_error_detail(text).class_name


@dataclass(frozen=True)
class ErrorMatch:
    class_name: str = ""
    phrase: str = ""          # the matched span, for explanations
    referent: str = ""        # path / id / object the error is ABOUT


def classify_error_detail(text: str) -> ErrorMatch:
    t = _err_key(text)
    hits: dict[str, str] = {}          # class -> longest matched span
    best_len, best_cls, best_span = 0, "", ""
    for cls, phrase, rx in _COMPILED:
        if phrase is not None:
            span = phrase if phrase in t else ""
        else:
            m = rx.search(t)  # type: ignore[union-attr]
            span = m.group(0) if m else ""
        if not span:
            continue
        if len(span) > len(hits.get(cls, "")):
            hits[cls] = span
        if len(span) > best_len:
            best_len, best_cls, best_span = len(span), cls, span
    if not best_cls:
        return ErrorMatch()
    # A family ROOT never outranks one of its own subclasses: "no such table"
    # is more informative than the bare "OperationalError" that precedes it,
    # even though the type name is the longer string. Cross-family ranking
    # stays purely longest-span (that is what makes "permission denied" beat
    # busybox's "can't open" in the same sentence).
    if best_cls == error_family(best_cls):
        sub = [(len(s), c) for c, s in hits.items()
               if c != best_cls and error_family(c) == best_cls]
        if sub:
            best_cls = max(sub)[1]
            best_span = hits[best_cls]
    return ErrorMatch(best_cls, best_span, extract_referent(text))


# ------------------------------------------------------ referent extraction
#
# The referent is WHAT the error is about: the path that was missing, the id
# that 404'd, the column whose constraint blew up. Same class + different
# referent = a wrong prediction, not a wording difference. Shared by gold and
# prediction so both are read the same way.
_REF_URL = re.compile(r"https?://[^\s'\"`,)]+")
_REF_AFTER_MARKER = re.compile(
    r"(?:no such table|no such column|unknown column|undefined column|"
    r"undefined table|constraint failed|has no column named|no module named)\s*:?\s*"
    r"['\"`]?([A-Za-z_][\w.$]*)",
    re.I,
)
_REF_TARGET_QUOTED = re.compile(
    r"(?:target|referent|resource|entity|object|record|file|path)\s*"
    r"(?:[=:]\s*)?['\"`]([^'\"`\n]{1,200})['\"`]",
    re.I,
)
_REF_QUOTED_BEFORE_ERROR = re.compile(
    r"['\"`]([^'\"`\n]{1,200})['\"`]\s*:\s*"
    r"(?:no such file or directory|permission denied|not a directory|"
    r"is a directory|file exists|device or resource busy)",
    re.I,
)
_REF_PATH_BEFORE_ERROR = re.compile(
    r"((?:/[A-Za-z0-9_.@+\-]+)+/?)\s*:\s*"
    r"(?:no such file or directory|permission denied|not a directory|"
    r"is a directory|file exists|device or resource busy)",
    re.I,
)
_REF_RELATIVE_PATH_BEFORE_ERROR = re.compile(
    r"(?<![A-Za-z0-9_.@+/\-])"
    r"([A-Za-z0-9_.@+\-]+(?:/[A-Za-z0-9_.@+\-]+)+)\s*:\s*"
    r"(?:no such file or directory|permission denied|not a directory|"
    r"is a directory|file exists|device or resource busy)",
    re.I,
)
_REF_QUOTED = re.compile(r"['\"`]([^'\"`\n]{1,200})['\"`]")
_REF_PATH = re.compile(r"(?:/[A-Za-z0-9_.@+\-]+)+/?")
_REF_DOTTED = re.compile(r"\b[a-z_][a-z0-9_\-]*\.[a-z_][a-z0-9_\-]{0,40}\b")
_REF_ID = re.compile(r"(?:\bid\s*[=: ]\s*|#)(\d+)\b", re.I)
_REF_EXCEPTION_START = re.compile(
    r"\b[A-Za-z_][\w.]*(?:error|exception|fault)\s*:", re.I
)
_STRIP_EDGES = " \t\n\r'\"`.,;:()[]{}"


def _referent_ok(cand: str) -> bool:
    c = cand.strip(_STRIP_EDGES)
    return bool(c) and not _WS.search(c)


def extract_referent(text: str) -> str:
    """The first referent named by an error text ("" if none).

    Priority: url > the identifier after a SQL "no such X:" marker > a
    quoted token > an absolute path > a dotted identifier (table.column,
    file.ext) > an explicit numeric id. Case-preserving.
    """
    t = _expand_contractions(normalize_text(text))
    # Traceback frames contain quoted filenames (often ``<stdin>``) before
    # the terminal exception. They are provenance, not the failed referent.
    # Restrict extraction to the last explicit exception clause so the actual
    # NameError/FileNotFoundError/AttributeError payload wins.
    exception_starts = list(_REF_EXCEPTION_START.finditer(t))
    if exception_starts:
        t = t[exception_starts[-1].start():]
    m = _REF_URL.search(t)
    if m:
        return m.group(0).strip(_STRIP_EDGES)
    m = _REF_AFTER_MARKER.search(t)
    if m:
        return m.group(1).strip(_STRIP_EDGES)
    m = _REF_TARGET_QUOTED.search(t)
    if m and _referent_ok(m.group(1)):
        return m.group(1).strip(_STRIP_EDGES)
    # Shell output often prints a successful path first and the failed path
    # later (for example ``readlink`` followed by ``cat``).  The path adjacent
    # to the terminal errno is the referent; an earlier output path is not.
    m = _REF_QUOTED_BEFORE_ERROR.search(t)
    if m and _referent_ok(m.group(1)):
        return m.group(1).strip(_STRIP_EDGES)
    m = _REF_RELATIVE_PATH_BEFORE_ERROR.search(t)
    if m:
        return m.group(1).strip(_STRIP_EDGES)
    m = _REF_PATH_BEFORE_ERROR.search(t)
    if m:
        return m.group(1).strip(_STRIP_EDGES)
    for m in _REF_QUOTED.finditer(t):
        # Quoted mapping keys are schema, not the failed object: in
        # {"error": "...target 'x'..."} the referent is 'x', not "error".
        prefix, suffix = t[:m.start()], t[m.end():]
        if re.search(r"(?:\{|,)\s*$", prefix) and re.match(r"\s*:", suffix):
            continue
        if _referent_ok(m.group(1)):
            return m.group(1).strip(_STRIP_EDGES)
    m = _REF_PATH.search(t)
    if m:
        return m.group(0).strip(_STRIP_EDGES)
    m = _REF_DOTTED.search(t)
    if m:
        return m.group(0).strip(_STRIP_EDGES)
    m = _REF_ID.search(t)
    if m:
        return m.group(1)
    return ""


def matches_error_class(text: str, declared: str) -> bool:
    """Does ``text`` read as the declared gold error class? Accepts a
    subclass of a declared family ("IntegrityError" <- FOREIGN_KEY)."""
    want = canonical_class(declared)
    got = classify_error(text)
    if not got or not want:
        return False
    return got == want or (want == error_family(want)
                           and error_family(got) == want)


# "<Something>Error:" / "...Exception:" / "...Fault:" -- the colon is
# required so an ordinary value that merely contains the word "error"
# (error_count=3) is not treated as error prose and given case-insensitivity.
_EXC_NAME = re.compile(r"\b[A-Za-z_][\w.]*(?:error|exception|fault)\s*:", re.I)
_MODULE_PREFIX = re.compile(r"\b[a-z][a-z0-9_]*\.(?=[A-Za-z_][A-Za-z0-9_]*"
                            r"(?:error|exception|fault)\b)", re.I)
_QUOTE_CHARS = re.compile(r"['\"`]")


def _looks_like_error(text: str) -> bool:
    return bool(classify_error(text)) or bool(_EXC_NAME.search(text))


def _prose_key(text: str) -> str:
    """Comparison key for error PROSE: module-qualifier-free, quote-style
    free, case-folded, whitespace-collapsed, terminal period dropped."""
    t = _MODULE_PREFIX.sub("", normalize_text(text))
    t = _QUOTE_CHARS.sub('"', t)
    return t.casefold().rstrip(".")


# ------------------------------------------------------------ order rules
_ORDER_BY = re.compile(r"\border\s+by\b", re.I)
_SELECTISH = re.compile(r"\A\s*(select|with)\b", re.I)


def order_sensitive_for_sql(sql: str) -> bool:
    """A SELECT without ORDER BY has arbitrary row order (the db executor
    documents this explicitly), so its rows must be graded unordered."""
    return bool(_ORDER_BY.search(sql))


def order_sensitive_for_item(item: ItemRecord) -> bool:
    """Per-item default for row-order strictness, read off the action."""
    args = item.action.args or ""
    if item.action.tool in {"sql", "db", "sqlite"} or _SELECTISH.match(args):
        return order_sensitive_for_sql(args)
    return True


def infer_scoring_mode(item: ItemRecord) -> str:
    """Derive the narrowest public scoring contract from an executed gold."""
    if item.item_shape == "post_action_probe" and item.probe is not None:
        return "probe"
    if parse_composite_error(item.gold.text) is not None:
        return "composite_error"
    ok, value = parse_structured(item.gold.text)
    if ok and _is_container(value):
        return "structured"
    if parse_content_claims(item.gold.text) is not None:
        return "claims"
    if item.gold.error_class or _looks_like_error(item.gold.text):
        return "error"
    return "exact"


def stamp_scoring_spec(item: ItemRecord) -> ItemRecord:
    """Materialize auto scoring choices before an item is serialized."""
    if item.scoring.mode == "auto":
        item.scoring.mode = infer_scoring_mode(item)  # type: ignore[assignment]
    if item.scoring.order_sensitive is None:
        item.scoring.order_sensitive = order_sensitive_for_item(item)
    return item


# ------------------------------------------------------------- the grader
@dataclass(frozen=True)
class GradeResult:
    correct: bool
    mode: str
    why: str
    achieved_level: str = "none"
    required_level: str = "referent"
    partial_credit: float = 0.0
    gold_family: str = ""
    pred_family: str = ""
    gold_class: str = ""
    pred_class: str = ""
    gold_referent: str = ""
    pred_referent: str = ""
    matched_claims: int = 0
    missing_claims: tuple[str, ...] = ()
    extra_claims: tuple[str, ...] = ()
    contradictory_claims: tuple[str, ...] = ()
    # True means the deterministic contract could neither certify semantic
    # equivalence nor identify a concrete contradiction. It remains
    # ``correct=False``; the runner routes it to the LLM judge instead of
    # reporting it as a deterministic failure.
    adjudication_required: bool = False


def _res(correct: bool, mode: str, why: str, notes: Sequence[str]) -> GradeResult:
    if notes:
        why = f"{why} [{'; '.join(notes)}]"
    return GradeResult(correct, mode, why)


def grade_detail(
    pred: str, gold_text: str, *, order_sensitive: bool = True,
    required_error_level: str = "referent",
) -> GradeResult:
    """Grade with an explanation. See the module docstring for the ladder."""
    levels = {"success_failure", "family", "class", "referent", "message"}
    if required_error_level not in levels:
        raise ValueError(f"unknown required_error_level {required_error_level!r}")
    pred = "" if pred is None else str(pred)
    gold_text = "" if gold_text is None else str(gold_text)
    prepped, notes = _prep_pred(pred, gold_text)

    gold_parsed, gold_value = parse_structured(gold_text)
    if not (gold_parsed and _is_container(gold_value)):
        unwrapped, note = _unwrap_singleton_answer(prepped)
        if note:
            prepped = unwrapped
            notes.append(note)

    g_norm, p_norm = normalize_text(gold_text), normalize_text(prepped)

    # 1. exact (whitespace-normalized, case-preserving)
    if g_norm == p_norm:
        base = _res(True, "exact", "normalized text identical", notes)
        if _looks_like_error(g_norm):
            m = classify_error_detail(g_norm)
            family = provider_neutral_family(m.class_name)
            return GradeResult(True, base.mode, base.why, "message",
                               required_error_level, 1.0,
                               family, family, m.class_name, m.class_name,
                               m.referent, m.referent)
        exact_ok, exact_value = parse_structured(gold_text)
        if exact_ok and _is_container(exact_value):
            return GradeResult(True, base.mode, base.why,
                               matched_claims=len(_flatten_structured(exact_value)))
        return base

    # 2. empty gold spelled out in words
    if g_norm == "" and p_norm.casefold() in EMPTY_SYNONYMS:
        return _res(True, "empty",
                    f"gold is empty output; pred {p_norm!r} says so", notes)
    if g_norm == "" or p_norm == "":
        which = "pred" if p_norm == "" else "gold"
        return _res(False, "mismatch", f"{which} is empty, the other is not",
                    notes)

    # 2b. a gold that is the REPR of a string, against the string itself.
    #
    # math's executor renders a value with repr(), so an expression returning a
    # STRING lands in the gold wrapped in quotes: srepr(M) gives
    #   'MutableDenseMatrix([[Integer(3), ...]])'
    # while an expression returning an int lands bare (7744). Nothing in the
    # trajectory teaches that distinction, so a model reproduces the content
    # and loses on two characters it could not have known to add.
    #
    # Narrow on purpose: it fires only when stripping ONE matched pair of outer
    # quotes from one side makes the two equal. It cannot rescue a prediction
    # that differs in any other way, and it never strips from both sides.
    for a, b in ((g_norm, p_norm), (p_norm, g_norm)):
        if len(a) >= 2 and a[0] == a[-1] and a[0] in "\"'" and a[1:-1] == b:
            return _res(True, "repr_quotes",
                        "one side is the repr of the other: identical content "
                        "wrapped in one pair of quotes the trajectory never "
                        "demonstrates", notes)

    # 2c. Composite generated errors: a structured audit snapshot plus its
    # terminal reason.  Surface notation is free; every state claim is not.
    g_composite = parse_composite_error(gold_text)
    if g_composite is not None:
        p_composite = parse_composite_error(prepped)
        if p_composite is None:
            return _res(False, "composite_error_missing",
                        "gold requires an audit mapping and terminal error; "
                        "prediction does not provide both", notes)
        audit_same = struct_eq(g_composite.audit, p_composite.audit, True)
        reason_same = g_composite.reason == p_composite.reason
        if audit_same and reason_same:
            return _res(True, "composite_error",
                        "audit mappings and terminal error reason agree", notes)
        differences = []
        if not audit_same:
            differences.append("audit mappings differ")
        if not reason_same:
            differences.append("terminal error reasons differ")
        return _res(False, "composite_error", "; ".join(differences), notes)

    # 3. structural (JSON row-sets, dicts, nested values)
    ok_g, gv = parse_structured(gold_text)
    ok_p, pv = parse_structured(prepped)
    if ok_g and ok_p and (_is_container(gv) or _is_container(pv)):
        if struct_eq(gv, pv, order_sensitive):
            how = "ordered" if order_sensitive else "order-insensitive"
            base = _res(True, "json",
                        f"canonical structures equal ({how} compare)", notes)
            n = len(_flatten_structured(gv))
            return GradeResult(base.correct, base.mode, base.why,
                               matched_claims=n)
        if order_sensitive and struct_eq(gv, pv, False):
            return _res(False, "json_order",
                        "same elements, different order; the gold query "
                        "imposed an order (ORDER BY) so order is graded",
                        notes)
        gc, pc = _flatten_structured(gv), _flatten_structured(pv)
        missing, extra, contradictory, matched = _claim_differences(gc, pc)
        # Semantic flexibility inside an explicitly named error FIELD is
        # allowed, but it can never hide a changed sibling state claim.
        semantic_error_paths = []
        for path in contradictory:
            if not path.casefold().endswith(".error"):
                continue
            g_error, p_error = gc[path], pc[path]
            if not isinstance(g_error, str) or not isinstance(p_error, str):
                continue
            nested = grade_detail(
                p_error, g_error, order_sensitive=True,
                required_error_level=required_error_level,
            )
            if nested.correct:
                semantic_error_paths.append(path)
        unresolved = tuple(
            path for path in contradictory if path not in semantic_error_paths
        )
        if not missing and not extra and not unresolved and semantic_error_paths:
            return GradeResult(
                True, "json_error", "structures agree; error fields are "
                "semantically equivalent", matched_claims=matched,
            )
        base = _res(False, "json", "canonical structures differ", notes)
        return GradeResult(base.correct, base.mode, base.why,
                           matched_claims=matched,
                           missing_claims=missing, extra_claims=extra,
                           contradictory_claims=unresolved)

    # 3b. Fully parsed domain-text claims.  This never extracts fragments
    # from prose: both sides must consist entirely of recognized lines.
    g_claims = parse_content_claims(gold_text)
    p_claims = parse_content_claims(prepped)
    if g_claims is not None and p_claims is not None:
        gd, pd = dict(g_claims.claims), dict(p_claims.claims)
        missing, extra, contradictory, matched = _claim_differences(gd, pd)
        same_order = tuple(k for k, _ in g_claims.claims) == tuple(
            k for k, _ in p_claims.claims)
        correct = not (missing or extra or contradictory) and (
            same_order or not order_sensitive)
        mode = "content_claims" if correct else (
            "content_claim_order" if not (missing or extra or contradictory)
            else "content_claims")
        why = ("all parsed claims agree" if correct else
               "claims agree but schema requires their order" if mode == "content_claim_order"
               else "parsed claims differ")
        base = _res(correct, mode, why, notes)
        return GradeResult(base.correct, base.mode, base.why,
                           matched_claims=matched,
                           missing_claims=missing, extra_claims=extra,
                           contradictory_claims=contradictory)
    if g_claims is not None and p_claims is None:
        # A matching error substring cannot erase the rest of an audit-shaped
        # gold. Route unparsed prose to semantic adjudication instead of
        # certifying a small matching subset.
        return GradeResult(
            False, "content_claims_unparsed",
            "gold is a complete claim surface but prediction is not",
            adjudication_required=True,
        )

    # 4. bare numeric scalars
    ng, np_ = _num(g_norm), _num(p_norm)
    if ng is not None and np_ is not None:
        ig, ip = ok_g and isinstance(gv, int), ok_p and isinstance(pv, int)
        same = (gv == pv) if (ig and ip and not isinstance(gv, bool)
                              and not isinstance(pv, bool)) else \
            math.isclose(ng, np_, rel_tol=REL_TOL, abs_tol=0.0)
        return _res(same, "numeric",
                    "numeric values equal" if same
                    else f"numeric values differ ({g_norm} vs {p_norm})",
                    notes)

    # 5/6. error surfaces
    # Compound commands can emit several independent terminal errors.
    # Matching just one class/referent is insufficient when gold requires two.
    def error_events(text: str) -> set[tuple[str, str]]:
        events = set()
        for line in text.splitlines():
            if not _looks_like_error(line):
                continue
            match = classify_error_detail(line)
            if match.class_name:
                events.add((match.class_name, match.referent))
        return events

    gold_events = error_events(gold_text)
    gold_lines = [line for line in gold_text.splitlines() if line.strip()]
    # Pytest tracebacks contain several incidental error-looking lines for one
    # terminal exception. Treat a gold as a true multi-error contract only
    # when every emitted line is itself an error event (as with two failing
    # commands in a compound shell action).
    pure_multi_error = (
        len(gold_events) > 1
        and gold_lines
        and all(_looks_like_error(line) for line in gold_lines)
    )
    if pure_multi_error:
        pred_events = error_events(prepped)
        if gold_events == pred_events:
            return _res(True, "multi_error_surface",
                        "all terminal error class/referent pairs agree", notes)
        missing = sorted(gold_events - pred_events)
        extra = sorted(pred_events - gold_events)
        return _res(False, "multi_error_surface",
                    f"terminal error sets differ; missing={missing}, extra={extra}",
                    notes)

    g_err, p_err = _looks_like_error(g_norm), _looks_like_error(p_norm)
    if g_err and p_err and _prose_key(g_norm) == _prose_key(p_norm):
        base = _res(True, "error_prose",
                    "identical error wording up to case/quote style", notes)
        return GradeResult(base.correct, base.mode, base.why, "message",
                           required_error_level, 1.0)

    gm, pm = classify_error_detail(g_norm), classify_error_detail(p_norm)
    if gm.class_name and pm.class_name:
        gf = provider_neutral_family(gm.class_name)
        pf = provider_neutral_family(pm.class_name)
        common = dict(required_level=required_error_level,
                      gold_family=gf, pred_family=pf,
                      gold_class=gm.class_name, pred_class=pm.class_name,
                      gold_referent=gm.referent, pred_referent=pm.referent)
        # A concretely wrong object is never accepted, even by a deliberately
        # broad configured threshold.
        if gm.referent and pm.referent and gm.referent != pm.referent:
            return GradeResult(False, "error_referent",
                               f"different referent: gold {gm.referent!r}, pred {pm.referent!r}",
                               "class" if gm.class_name == pm.class_name else
                               ("family" if gf == pf else "success_failure"),
                               partial_credit=0.0, **common)
        if gf != pf:
            return GradeResult(False, "error_family_mismatch",
                               f"different broad family: gold {gf}, pred {pf}",
                               "success_failure", partial_credit=.2, **common)
        if gm.class_name != pm.class_name:
            rel = ("same family, different class"
                   if error_family(gm.class_name) == error_family(pm.class_name)
                   else "different error class")
            correct = required_error_level in {"success_failure", "family"}
            return GradeResult(correct, "error_class_mismatch",
                               f"{rel}: gold {gm.class_name}, pred {pm.class_name}",
                               "family", partial_credit=.4, **common)
        ok_ref, why_ref = _referents_agree(gm, pm, g_norm, p_norm)
        if ok_ref:
            # Referential fidelity is vacuously satisfied when the gold does
            # not identify an object; there is no hidden referent to guess.
            achieved = "referent"
            rank = {"success_failure": 0, "family": 1, "class": 2,
                    "referent": 3, "message": 4}
            correct = rank[achieved] >= rank[required_error_level]
            return GradeResult(correct, "error_class",
                               f"same error class {gm.class_name}; {why_ref}",
                               achieved, partial_credit=.8 if achieved == "referent" else .6,
                               **common)
        return GradeResult(False, "error_referent",
                           f"error class {gm.class_name} matches but {why_ref}",
                           "class", partial_credit=0.0, **common)
    if gm.class_name and not pm.class_name:
        return _res(False, "error_missing",
                    f"gold is error class {gm.class_name}; pred does not "
                    "read as that error", notes)
    if pm.class_name and not gm.class_name:
        return _res(False, "error_spurious",
                    f"pred claims error class {pm.class_name}; gold is not "
                    "an error", notes)

    base = _res(False, "mismatch", "texts differ and no rule applies", notes)
    return GradeResult(**{
        **base.__dict__,
        "adjudication_required": True,
    })


def _referents_agree(
    gm: ErrorMatch, pm: ErrorMatch, g_norm: str, p_norm: str
) -> tuple[bool, str]:
    """Referent policy (asymmetric on purpose):

    - gold names no referent -> nothing to check.
    - gold names one, pred names one -> they must be equal.
    - gold names one, pred names none -> the gold's referent must at least
      appear verbatim in the prediction, otherwise the prediction is a
      class-shaped guess that never commits to the object (so a constant
      error guess cannot pass).
    - pred names an extra referent the gold lacks -> allowed (drivers add
      constraint names, hostnames, etc.).
    """
    if not gm.referent:
        return True, "gold names no referent"
    if pm.referent:
        if pm.referent == gm.referent:
            return True, f"same referent {gm.referent!r}"
        return False, (f"different referent: gold {gm.referent!r}, "
                       f"pred {pm.referent!r}")
    if gm.referent in p_norm:
        return True, f"pred names the gold referent {gm.referent!r}"
    return False, f"pred never names the gold referent {gm.referent!r}"


def grade(pred: str, gold_text: str, *, order_sensitive: bool = True,
          required_error_level: str = "referent") -> bool:
    """Boolean form of :func:`grade_detail`."""
    return grade_detail(pred, gold_text, order_sensitive=order_sensitive,
                        required_error_level=required_error_level).correct


def make_grader(*, order_sensitive: bool = True,
                required_error_level: str = "referent") -> Callable[[str, str], bool]:
    """A ``(pred, gold) -> bool`` closure with the order policy fixed."""
    def _g(pred: str, gold_text: str) -> bool:
        return grade(pred, gold_text, order_sensitive=order_sensitive,
                     required_error_level=required_error_level)
    return _g


# --------------------------------------------- change-set / frame scoring
def _canon_value_key(v: Any) -> str:
    """Hashable canonical key for a ChangeTuple ``after`` value: numbers by
    value (so 1 == "1" == 1.0), booleans and nulls by word, everything else
    by whitespace-collapsed text."""
    if isinstance(v, bool):
        return f"b:{str(v).lower()}"
    if v is None:
        return "n:null"
    if isinstance(v, str):
        s = normalize_text(v)
        low = s.casefold()
        if low in ("true", "false"):
            return f"b:{low}"
        if low in _NULL_WORDS:
            return "n:null"
        f = _num(s)
        if f is not None:
            return _canon_value_key(int(f) if f.is_integer() else f)
        return f"s:{s}"
    if isinstance(v, int):
        return f"num:{v}"                       # exact: ints never round
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 2 ** 53:
            return f"num:{int(v)}"              # 73.0 and 73 are one value
        return f"num:{v:.12g}"                  # 12 sig figs ~ the float tol
    if isinstance(v, (list, tuple, dict)):
        return "j:" + json.dumps(_jsonable(v), sort_keys=True, default=str)
    return f"s:{normalize_text(str(v))}"


def _triple(t: Any) -> tuple[str, str, str]:
    """Accept ChangeTuple, dict, or (entity, attribute, after[, ...])."""
    if isinstance(t, ChangeTuple):
        ent, attr, after = t.entity, t.attribute, t.after
    elif isinstance(t, dict):
        ent = t.get("entity", "")
        attr = t.get("attribute", "")
        after = t.get("after")
    elif isinstance(t, (tuple, list)):
        if len(t) < 3:
            raise ValueError(f"change tuple needs >=3 fields: {t!r}")
        ent, attr, after = t[0], t[1], t[2]
    else:
        raise TypeError(f"unsupported change tuple {type(t).__name__}")
    return (normalize_text(str(ent)), normalize_text(str(attr)),
            _canon_value_key(after))


@dataclass(frozen=True)
class ChangeSetScore:
    recall: float
    precision: float
    f1: float
    matched: tuple[tuple[str, str, str], ...] = ()
    missed: tuple[tuple[str, str, str], ...] = ()     # under-propagation
    extra: tuple[tuple[str, str, str], ...] = ()      # over-propagation


def grade_change_set_detail(
    pred_tuples: Iterable[Any], gold_tuples: Iterable[Any]
) -> ChangeSetScore:
    """Set-scoring over (entity, attribute, after) triples.

    Recall = did the model find the changes that happened (under-propagation
    when < 1). Precision = did it invent changes that did not (phantom
    effects / over-propagation when < 1). An L0 item has an empty gold set:
    predicting nothing scores 1/1, and every phantom change drives precision
    to 0.
    """
    gold = Counter(_triple(t) for t in gold_tuples)
    pred = Counter(_triple(t) for t in pred_tuples)
    inter = gold & pred
    n_match = sum(inter.values())
    n_gold, n_pred = sum(gold.values()), sum(pred.values())
    recall = 1.0 if n_gold == 0 else n_match / n_gold
    precision = 1.0 if n_pred == 0 else n_match / n_pred
    f1 = 0.0 if (recall + precision) == 0 else (
        2 * recall * precision / (recall + precision)
    )
    return ChangeSetScore(
        recall=recall, precision=precision, f1=f1,
        matched=tuple(sorted(inter.elements())),
        missed=tuple(sorted((gold - pred).elements())),
        extra=tuple(sorted((pred - gold).elements())),
    )


def grade_change_set(
    pred_tuples: Iterable[Any], gold_tuples: Iterable[Any]
) -> tuple[float, float, float]:
    """(recall, precision, f1) over (entity, attribute, after) triples."""
    s = grade_change_set_detail(pred_tuples, gold_tuples)
    return (s.recall, s.precision, s.f1)


def frame_violations(
    pred_tuples: Iterable[Any], frame_entities: Sequence[str]
) -> list[str]:
    """Frame entities (the must-not-change set) that a prediction claims
    changed = phantom effects. Sorted, deduplicated."""
    frame = {normalize_text(e) for e in frame_entities}
    hit = {ent for ent, _attr, _after in (_triple(t) for t in pred_tuples)
           if ent in frame}
    return sorted(hit)


# ------------------------------------------------------------ probe items
@dataclass(frozen=True)
class ProbeScore:
    role: str
    correct: bool
    mode: str
    why: str
    failure_kind: str = ""   # under_propagation / over_propagation /
    #                          surface_mismatch ("" when correct)


_FAILURE_KIND = {
    "recall": "under_propagation",     # missed a change that happened
    "precision": "over_propagation",   # invented a change that did not
    "surface": "surface_mismatch",     # secondary surface read wrong
}


def score_probe(
    item: ItemRecord, pred_text: str, *, order_sensitive: bool | None = None
) -> ProbeScore:
    """Grade one post_action_probe item, dispatching on ``probe.probe_role``.

    All three roles are graded with the same text grader (the gold is an
    execution-derived READ either way); the role decides how a FAILURE is
    labelled, which is what the radius tables report:
      recall    -> the read reveals the mutation; wrong = under-propagation
      precision -> the read is a must-not-change surface; wrong = a phantom
                   change (over-propagation)
      surface   -> a secondary surface (audit count, free space)
    """
    if item.probe is None:
        raise ValueError("score_probe requires an item with a probe "
                         "(item_shape=post_action_probe)")
    role = item.probe.probe_role
    if order_sensitive is None:
        order_sensitive = order_sensitive_for_item(item)
    r = grade_detail(pred_text, item.gold.text, order_sensitive=order_sensitive)
    return ProbeScore(
        role=role,
        correct=r.correct,
        mode=r.mode,
        why=r.why,
        failure_kind="" if r.correct else _FAILURE_KIND.get(role, "mismatch"),
    )
