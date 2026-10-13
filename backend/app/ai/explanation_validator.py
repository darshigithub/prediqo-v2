"""Shared semantic, structural, and factual integrity validator for AI Business Explanations.
Distinguishes positive guarantee/causal claims from valid disclaimers and negated statements.
"""
from __future__ import annotations

import re
from typing import Any

# Standard list of terms that assert unverified certainty when un-negated
FORBIDDEN_GUARANTEE_TERMS = [
    "guaranteed profit",
    "guaranteed return",
    "guaranteed outcome",
    "100% certain",
    "will definitely happen",
    "will certainly occur",
    "directly causes",
    "proven cause",
]

# Positive guarantee / certainty patterns that assert an outcome or metric is guaranteed

POSITIVE_GUARANTEE_PATTERNS = [
    re.compile(
        r"\b(?:guarantees?|guaranteeing|guaranteed|assures?|ensures?)\b[^\.\;\!\n]{0,45}\b(?:outcome|profit|return|result|success|revenue|growth|performance|target|gain|accuracy|sales|demand|value)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:outcome|profit|return|result|success|revenue|sales)\b[^\.\;\!\n]{0,30}\bis\s+(?:guaranteed|assured|certain)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b100%\s*(?:certain|guaranteed|sure|accurate|reliable)\b", re.IGNORECASE),
    re.compile(r"\b(?:will\s+definitely|will\s+certainly)\s+(?:happen|occur|reach|exceed|generate|result|deliver)\b", re.IGNORECASE),
    re.compile(r"\bcertain\s+to\s+(?:happen|occur|succeed|result|exceed)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+(?:completely\s+)?risk-?free\b", re.IGNORECASE),
    re.compile(r"\bdirectly\s+causes?\b", re.IGNORECASE),
    re.compile(r"\bproven\s+cause\b", re.IGNORECASE),
]

# Negation and disclaimer patterns that neutralize what would otherwise look like a guarantee
NEGATION_DISCLAIMER_PATTERNS = [
    re.compile(
        r"\b(?:not|no|never|cannot|can't|does\s+not|doesn't|is\s+not|isn't|are\s+not|aren't|do\s+not|don't|without|unlikely|neither|nor|instead\s+of|rather\s+than)\b[^\.\;\!\n]{0,60}\b(?:guarantee|guaranteed|certain|definitely|certainly|causes?|proven\s+cause)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:guarantee|guaranteed|certain|definitely|certainly|causes?)\b[^\.\;\!\n]{0,40}\b(?:is\s+not|are\s+not|cannot\s+be|is\s+never|are\s+never|does\s+not)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:statistical\s+ranges?|statistical\s+bounds?|distributional\s+intervals?|estimates?)\s*,\s*not\s+(?:a\s+)?guaranteed\b", re.IGNORECASE),
    re.compile(r"\bnot\s+(?:a\s+)?guaranteed\s+outcome\b", re.IGNORECASE),
    re.compile(r"\bdoes\s+not\s+(?:constitute|imply|represent|mean)\s+(?:a\s+)?guarantee\b", re.IGNORECASE),
    re.compile(r"\bdoes\s+not\s+directly\s+cause\b", re.IGNORECASE),
    re.compile(r"\bcorrelation\s+(?:is\s+not|does\s+not\s+imply)\s+causation\b", re.IGNORECASE),
    re.compile(r"\bactual\s+(?:results|outcomes)\s+may\s+differ\b", re.IGNORECASE),
    re.compile(r"\bestimates?\s+based\s+on\s+(?:the\s+)?available\s+data\b", re.IGNORECASE),
]

REQUIRED_EXPLANATION_KEYS = [
    "summary",
    "what_the_result_means",
    "supporting_evidence",
    "evaluation_quality",
    "uncertainty_and_limitations",
    "suggested_verifications",
]


def split_into_clauses(text: str) -> list[str]:
    """Splits text into distinct sentences and clause chunks for context-aware safety evaluation."""
    raw_sentences = re.split(r"[\.\!\?\;\n•\r]+", text)
    clauses: list[str] = []
    for s in raw_sentences:
        clean = s.strip()
        if clean:
            clauses.append(clean)
    return clauses


def is_clause_negated_or_disclaimer(clause: str) -> bool:
    """Returns True if the clause contains a recognized negation or disclaimer pattern."""
    for pattern in NEGATION_DISCLAIMER_PATTERNS:
        if pattern.search(clause):
            return True
    return False


def evaluate_clause_guarantees(clause: str) -> tuple[bool, str]:
    """Evaluates an individual clause for positive guarantee or unsupported causal claims.
    
    Returns:
        (is_valid, violation_detail)
    """
    # 1. If the clause explicitly includes negation or disclaimer context, it is safe
    if is_clause_negated_or_disclaimer(clause):
        return True, ""

    # 2. Check against positive guarantee assertions
    for pattern in POSITIVE_GUARANTEE_PATTERNS:
        match = pattern.search(clause)
        if match:
            matched_phrase = match.group(0).strip()
            return False, f"Positive guarantee/causal claim detected: '{matched_phrase}'"

    return True, ""


def validate_explanation_integrity(
    raw_exp: dict[str, Any],
    evidence: dict[str, Any],
    exp_type: str = "prediction",
) -> tuple[bool, str]:
    """Validates that the explanation response satisfies structural, semantic, and non-guarantee standards.
    
    Returns:
        (is_valid, reason_message)
    """
    if not isinstance(raw_exp, dict):
        return False, "Explanation response must be a JSON object"

    # 1. Structural schema validation
    for key in REQUIRED_EXPLANATION_KEYS:
        if key not in raw_exp:
            return False, f"Missing required explanation field: '{key}'"
        val = raw_exp[key]
        if isinstance(val, str) and not val.strip():
            return False, f"Empty string in explanation field: '{key}'"
        if isinstance(val, list) and len(val) == 0:
            return False, f"Empty list in explanation field: '{key}'"

    # 2. Extract and check all textual content across sections
    text_sections = [
        raw_exp.get("summary", ""),
        raw_exp.get("what_the_result_means", ""),
        raw_exp.get("evaluation_quality", ""),
    ]
    for bullet in raw_exp.get("supporting_evidence", []):
        if isinstance(bullet, str):
            text_sections.append(bullet)
    for bullet in raw_exp.get("uncertainty_and_limitations", []):
        if isinstance(bullet, str):
            text_sections.append(bullet)
    for bullet in raw_exp.get("suggested_verifications", []):
        if isinstance(bullet, str):
            text_sections.append(bullet)

    full_text = " ".join(text_sections)
    clauses = split_into_clauses(full_text)

    # 3. Context-aware clause analysis
    for clause in clauses:
        valid, reason = evaluate_clause_guarantees(clause)
        if not valid:
            return False, reason

    # 4. Calibration truth check (uncalibrated probability claiming to be calibrated)
    prob_type = evidence.get("problem_type") or ("forecasting" if exp_type == "forecast" else "regression")
    if prob_type == "classification":
        full_lower = full_text.lower()
        if "calibrated true probability" in full_lower or "proven calibrated confidence" in full_lower:
            return False, "Uncalibrated classification score incorrectly labeled as calibrated real-world probability"

    return True, ""
