"""Answer generation helpers for GraphRAG."""

from __future__ import annotations

from typing import Any, Iterable

from openai import OpenAI


SYSTEM_PROMPT = "GraphRAG assistant"


def _extract_sources(context: Any) -> list[str]:
    """Extract source references from multiple context shapes."""
    if context is None:
        return []

    if isinstance(context, dict):
        raw_sources = context.get("sources", [])
    elif isinstance(context, list) and context and isinstance(context[0], dict):
        raw_sources = [item.get("source") for item in context if item.get("source")]
    else:
        return []

    sources: list[str] = []
    for source in raw_sources:
        if source:
            sources.append(str(source))
    return sources


def _context_to_text(context: Any) -> str:
    """Convert context payload to readable text for the LLM prompt."""
    if context is None:
        return ""

    if isinstance(context, dict):
        if isinstance(context.get("chunks"), Iterable):
            chunks = [str(chunk) for chunk in context.get("chunks", [])]
            return "\n\n".join(chunks)
        return str(context.get("text", context))

    if isinstance(context, list):
        lines: list[str] = []
        for item in context:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                source = item.get("source")
                if source:
                    lines.append(f"[{source}] {text}".strip())
                else:
                    lines.append(str(text))
            else:
                lines.append(str(item))
        return "\n\n".join([line for line in lines if line])

    return str(context)


def generate_answer(query: str, context: Any, model: str = "gpt-4o-mini") -> str:
    """
    Generate an answer with OpenAI Chat Completions.

    The answer must include source citations from the provided GraphRAG context.
    """
    client = OpenAI()

    sources = _extract_sources(context)
    context_text = _context_to_text(context)

    source_instruction = (
        "Use and cite these sources in the final answer: " + ", ".join(sources)
        if sources
        else "If no explicit sources are provided, state that no sources were available."
    )

    user_prompt = (
        f"Query:\n{query}\n\n"
        f"Context:\n{context_text}\n\n"
        f"{source_instruction}\n"
        "Always end your answer with a 'Sources:' section."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or ""
