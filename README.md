# graphRAG

A minimal response contract for GraphRAG-style chat results.

## Chat response layout

Every chat response should contain these sections:

1. **Answer**: the natural-language response to the user.
2. **Sources**: citations or references used to produce the answer.
3. **Entities**: extracted named entities (people, orgs, systems, etc.).
4. **View Graph**: graph-oriented relationships connecting the entities.

## Markdown template

Use the template in `templates/chat_response.md` to keep output consistent.
