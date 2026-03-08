from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


_CLASSIFICATION_FIELDS = (
    "canonical_name",
    "alternate_names",
    "site_types",
    "primary_type",
    "description",
    "tags",
    "raw_name",
    "raw_type",
    "raw_subtype",
    "raw_description",
)

_INCLUDE_RULES: tuple[tuple[str, str, str], ...] = (
    ("include:stone circle", "stone circle", "specific"),
    ("include:stone ring", "stone ring", "specific"),
    ("include:recumbent stone circle", "recumbent stone circle", "specific"),
    ("include:standing stones", "standing stones", "specific"),
    ("include:stone setting", "stone setting", "specific"),
    ("include:stone row", "stone row", "specific"),
    ("include:henge and stone circle", "henge and stone circle", "specific"),
    ("include:megalithic monument", "megalithic monument", "broad"),
    ("include:megalithic", "megalithic", "broad"),
    ("include:megalith", "megalith", "broad"),
)

_REVIEW_RULES: tuple[tuple[str, str], ...] = (
    ("review:ring cairn", "ring cairn"),
    ("review:cairn circle", "cairn circle"),
    ("review:timber circle", "timber circle"),
    ("review:ritual monument", "ritual monument"),
    ("review:prehistoric enclosure", "prehistoric enclosure"),
)

_EXCLUDE_RULES: tuple[tuple[str, str], ...] = (
    ("exclude:church", "church"),
    ("exclude:priory", "priory"),
    ("exclude:abbey", "abbey"),
    ("exclude:cathedral", "cathedral"),
    ("exclude:castle", "castle"),
    ("exclude:bridge", "bridge"),
    ("exclude:railway", "railway"),
    ("exclude:viaduct", "viaduct"),
    ("exclude:house", "house"),
    ("exclude:hall", "hall"),
    ("exclude:farmstead", "farmstead"),
    ("exclude:mill", "mill"),
    ("exclude:industrial", "industrial"),
    ("exclude:fort", "fort"),
)


@dataclass(frozen=True)
class ClassificationDecision:
    classification: str
    classification_reason: str
    classification_rules_matched: list[str]
    classification_confidence: str


def classify_record(record: dict[str, Any]) -> ClassificationDecision:
    haystack = _record_text(record)

    include_matches = _matched_rule_labels(_INCLUDE_RULES, haystack)
    review_matches = _matched_rule_labels(_REVIEW_RULES, haystack)
    exclude_matches = _matched_rule_labels(_EXCLUDE_RULES, haystack)

    matched_labels = include_matches + review_matches + exclude_matches

    matched_specific_include = any(label in _specific_include_labels() for label in include_matches)
    matched_broad_include = bool(include_matches) and not matched_specific_include

    if matched_specific_include:
        if exclude_matches:
            return ClassificationDecision(
                classification="included",
                classification_reason="Specific megalith term overrides exclude term",
                classification_rules_matched=matched_labels,
                classification_confidence="high",
            )
        return ClassificationDecision(
            classification="included",
            classification_reason="Matched megalith-specific include term",
            classification_rules_matched=matched_labels,
            classification_confidence="high",
        )

    if matched_broad_include:
        if review_matches or exclude_matches:
            return ClassificationDecision(
                classification="review",
                classification_reason="Broad megalith term requires review",
                classification_rules_matched=matched_labels,
                classification_confidence="medium",
            )
        return ClassificationDecision(
            classification="included",
            classification_reason="Matched broad megalith include term",
            classification_rules_matched=matched_labels,
            classification_confidence="medium",
        )

    if review_matches:
        return ClassificationDecision(
            classification="review",
            classification_reason="Matched ambiguous monument term",
            classification_rules_matched=matched_labels,
            classification_confidence="medium",
        )

    if exclude_matches:
        return ClassificationDecision(
            classification="excluded",
            classification_reason="Matched non-megalith exclude term",
            classification_rules_matched=matched_labels,
            classification_confidence="high",
        )

    return ClassificationDecision(
        classification="review",
        classification_reason="No classification rules matched",
        classification_rules_matched=[],
        classification_confidence="low",
    )


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for field_name in _CLASSIFICATION_FIELDS:
        value = record.get(field_name)
        if value is None:
            continue
        if isinstance(value, str):
            parts.append(value)
            continue
        if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
            parts.extend(str(item) for item in value if item is not None)
            continue
        parts.append(str(value))
    return " ".join(parts).lower()


def _matched_rule_labels(
    rules: Iterable[tuple[str, str] | tuple[str, str, str]],
    haystack: str,
) -> list[str]:
    matched: list[tuple[str, str]] = []
    for rule in rules:
        label, phrase = rule[0], rule[1]
        if phrase in haystack:
            matched.append((label, phrase))
    return _drop_subsumed_matches(matched)


def _drop_subsumed_matches(matches: list[tuple[str, str]]) -> list[str]:
    labels: list[str] = []
    phrases = [phrase for _, phrase in matches]
    for label, phrase in matches:
        if any(
            phrase != other_phrase and phrase in other_phrase
            for other_phrase in phrases
        ):
            continue
        labels.append(label)
    return labels


def _specific_include_labels() -> set[str]:
    return {
        label
        for label, _, specificity in _INCLUDE_RULES
        if specificity == "specific"
    }
