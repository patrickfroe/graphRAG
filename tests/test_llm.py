from types import SimpleNamespace

from app.llm import LLMService


class DummyCompletions:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Antwort aus Chunks"))]
        )


class DummyClient:
    def __init__(self, completions: DummyCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def test_answer_uses_strict_prompt_and_zero_temperature(monkeypatch):
    completions = DummyCompletions()
    service = LLMService.__new__(LLMService)
    service.model = "test-model"
    service.client = DummyClient(completions)

    answer = service.answer("Was steht über Alice?", ["Alice kennt Bob.", "Alice arbeitet bei ACME."])

    assert answer == "Antwort aus Chunks"
    assert completions.kwargs is not None
    assert completions.kwargs["temperature"] == 0.0

    system_message = completions.kwargs["messages"][0]["content"]
    user_message = completions.kwargs["messages"][1]["content"]

    assert "nur Informationen aus den gelieferten Chunks" in system_message
    assert "[CHUNK 1]" in user_message
    assert "[CHUNK 2]" in user_message
    assert "Erfinde keine Fakten" in user_message


def test_answer_handles_missing_chunks(monkeypatch):
    completions = DummyCompletions()
    service = LLMService.__new__(LLMService)
    service.model = "test-model"
    service.client = DummyClient(completions)

    service.answer("Gibt es Infos zu Carol?", [])

    user_message = completions.kwargs["messages"][1]["content"]
    assert "(keine Chunks gefunden)" in user_message
    assert "keine verlässliche Information" in user_message
