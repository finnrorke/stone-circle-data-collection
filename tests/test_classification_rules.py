from __future__ import annotations

from dataset_collection.classification_rules import classify_record


def test_include_keyword_causes_included_classification() -> None:
    decision = classify_record({"canonical_name": "Boscawen Stone Circle"})

    assert decision.classification == "included"
    assert decision.classification_reason == "Matched megalith-specific include term"
    assert decision.classification_rules_matched == ["include:stone circle"]
    assert decision.classification_confidence == "high"


def test_review_keyword_causes_review_classification() -> None:
    decision = classify_record({"description": "A probable ring cairn on the ridge."})

    assert decision.classification == "review"
    assert decision.classification_reason == "Matched ambiguous monument term"
    assert decision.classification_rules_matched == ["review:ring cairn"]
    assert decision.classification_confidence == "medium"


def test_exclude_keyword_causes_excluded_classification() -> None:
    decision = classify_record({"raw_type": "Church"})

    assert decision.classification == "excluded"
    assert decision.classification_reason == "Matched non-megalith exclude term"
    assert decision.classification_rules_matched == ["exclude:church"]
    assert decision.classification_confidence == "high"


def test_include_beats_exclude_for_highly_specific_megalith_terms() -> None:
    decision = classify_record(
        {
            "description": "Standing stones survive inside a later fort earthwork.",
        }
    )

    assert decision.classification == "included"
    assert decision.classification_reason == "Specific megalith term overrides exclude term"
    assert decision.classification_rules_matched == [
        "include:standing stones",
        "exclude:fort",
    ]
    assert decision.classification_confidence == "high"


def test_no_keyword_match_defaults_to_review() -> None:
    decision = classify_record({"canonical_name": "North Field"})

    assert decision.classification == "review"
    assert decision.classification_reason == "No classification rules matched"
    assert decision.classification_rules_matched == []
    assert decision.classification_confidence == "low"


def test_matching_is_case_insensitive() -> None:
    decision = classify_record({"primary_type": "ReCuMbEnT StOnE CiRcLe"})

    assert decision.classification == "included"
    assert decision.classification_rules_matched == ["include:recumbent stone circle"]
    assert decision.classification_confidence == "high"


def test_multiple_matching_fields_are_considered() -> None:
    decision = classify_record(
        {
            "canonical_name": "Tor Hill",
            "alternate_names": ["Old Stone Ring"],
            "raw_description": "Fragmentary standing stones remain visible.",
        }
    )

    assert decision.classification == "included"
    assert decision.classification_rules_matched == [
        "include:stone ring",
        "include:standing stones",
    ]
