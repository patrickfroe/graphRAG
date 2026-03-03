import asyncio

from app.entity_extraction import (
    evaluate_entities,
    extract_entities_batch,
    merge_entities,
    normalize_entity_name,
    rank_entities,
    ExtractedEntity,
)


def test_normalize_entity_name_removes_punctuation_and_case():
    assert normalize_entity_name(" Microsoft, Inc. ") == "microsoft inc"


def test_merge_entities_deduplicates_by_normalization_and_fuzzy_match():
    gliner_entities = [
        {"text": "Microsoft", "type": "organization", "confidence": 0.92},
        {"text": "Satya Nadella", "type": "person", "confidence": 0.9},
    ]
    llm_entities = [
        {"text": "microsoft.", "type": "company", "confidence": 0.75},
        {"text": "Satya Nadela", "type": "person", "confidence": 0.7},
    ]

    merged = merge_entities(gliner_entities, llm_entities)

    assert len(merged) == 2
    names = {entity["text"] for entity in merged}
    assert "Microsoft" in names
    assert "Satya Nadella" in names


def test_rank_entities_scores_frequency_and_confidence():
    entities = [
        ExtractedEntity(text="Microsoft", type="company", confidence=0.9, chunk_ids={"c1", "c2"}),
        ExtractedEntity(text="Rare", type="project", confidence=0.1, chunk_ids={"c3"}),
    ]

    ranked = rank_entities(entities)

    assert len(ranked) == 2
    assert ranked[0]["name"] == "Microsoft"
    assert ranked[0]["score"] == 2 * 0.6 + 0.9 * 0.4



def test_evaluate_entities_precision_recall():
    metrics = evaluate_entities(["Microsoft", "Satya Nadella"], ["microsoft", "OpenAI"])

    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["entity_frequency"] == 2.0


def test_extract_entities_batch_returns_entities_and_relationships():
    chunks = [{"chunk_id": "c1", "text": "Satya Nadella works at Microsoft."}]

    def fake_gliner(_: str):
        return [{"text": "Satya Nadella", "type": "person", "confidence": 0.91}]

    def fake_llm(_: str):
        return [{"text": "Microsoft", "type": "company", "confidence": 0.75}]

    def fake_rel(_: str):
        return [{"source": "Satya Nadella", "target": "Microsoft", "type": "WORKS_FOR"}]

    result = asyncio.run(
        extract_entities_batch(
            chunks,
            gliner_extractor=fake_gliner,
            llm_extractor=fake_llm,
            relationship_extractor=fake_rel,
        )
    )

    assert len(result["entities"]) == 2
    assert result["relationships"] == [
        {"source": "Satya Nadella", "target": "Microsoft", "type": "WORKS_FOR", "chunk_id": "c1"}
    ]
