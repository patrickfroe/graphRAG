from fastapi import FastAPI, Query

app = FastAPI()


def build_preview(entity_keys: list[str]) -> dict:
    nodes = [
        {"id": key, "label": key, "type": "entity"}
        for key in entity_keys
    ]

    edges = [
        {
            "source": entity_keys[idx],
            "target": entity_keys[idx + 1],
            "label": "related_to",
        }
        for idx in range(len(entity_keys) - 1)
    ]

    return {"nodes": nodes, "edges": edges}


@app.get("/graph/preview")
def graph_preview(entity_keys: str = Query(default="")) -> dict:
    keys = [key.strip() for key in entity_keys.split(",") if key.strip()]
    return build_preview(keys)
