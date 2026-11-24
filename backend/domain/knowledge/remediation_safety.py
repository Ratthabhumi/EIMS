"""Pure helpers that decide whether remediation text *instructs* a state-changing action.

Why this exists: a keyword scan treats "Do not delete separate backup files manually" and "No remediation: this is a requested
action" as destructive remediation, because the sentence contains "delete" or "restart". A prohibition is the opposite of an
instruction, so it must not make a record "high risk". The rule is deliberately narrow and conservative:

* the text is split into sentences;
* a sentence is a *prohibition* only if a negation or avoidance cue occurs **before** the first destructive verb in that same
  sentence (e.g. "Do not ...", "never ...", "it is not necessary or desirable to ...", "avoid ...", "No remediation: ...");
* every other sentence that contains a destructive verb counts as an instruction (fail towards "destructive").

``DESTRUCTIVE_VERBS`` is the single source of truth for the register, the validator and the adapter.
"""
from __future__ import annotations

import re

DESTRUCTIVE_VERBS = (
    "delete", "remove", "drop", "truncate", "wipe", "erase", "reset", "disable", "stop", "kill", "format", "purge", "destroy",
    "overwrite", "detach", "shutdown", "failover", "rebuild", "restart", "reboot",
)
DESTRUCTIVE_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, DESTRUCTIVE_VERBS)) + r")\b", re.I)
_NEGATION = re.compile(
    r"\b(?:do not|don't|dont|never|avoid|should not|must not|cannot|can't|not necessary|not desirable|no remediation|is not recommended|not recommended)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?;])\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text or "") if s.strip()]


def is_prohibition(sentence: str) -> bool:
    """True when a negation/avoidance cue precedes the first destructive verb of the sentence."""
    verb = DESTRUCTIVE_RE.search(sentence)
    if not verb:
        return False
    neg = _NEGATION.search(sentence)
    return bool(neg) and neg.start() < verb.start()


def destructive_actions(texts: list[str] | tuple[str, ...]) -> list[str]:
    """Sentences that instruct a state-changing action (verbs inside prohibitions are ignored)."""
    out: list[str] = []
    for text in texts:
        for sentence in sentences(str(text)):
            if DESTRUCTIVE_RE.search(sentence) and not is_prohibition(sentence):
                out.append(sentence)
    return out


def destructive_verbs_in(texts: list[str] | tuple[str, ...]) -> list[str]:
    return sorted({m.group(0).casefold() for s in destructive_actions(texts) for m in DESTRUCTIVE_RE.finditer(s)})


# EIMS governance rule (not a vendor statement): a remediation that instructs a state-changing action is never executed without an
# explicit human approval. Vendor documentation does not state approval policy, so the adapter reports this rule with origin "eims_policy".
DESTRUCTIVE_ACTION_POLICY = "Destructive or state-changing actions require explicit human approval before execution (EIMS policy)."
