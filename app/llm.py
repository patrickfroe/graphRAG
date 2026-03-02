from openai import OpenAI

from app.config import get_settings


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_chat_model
        self.client = OpenAI(api_key=settings.openai_api_key)

    def answer(self, query: str, context_chunks: list[str]) -> str:
        rendered_chunks = [
            f"[CHUNK {index}]\n{chunk.strip()}"
            for index, chunk in enumerate(context_chunks, start=1)
            if chunk and chunk.strip()
        ]
        context = "\n\n".join(rendered_chunks) if rendered_chunks else "(keine Chunks gefunden)"
        prompt = (
            "Frage des Nutzers:\n"
            f"{query}\n\n"
            "Verfügbare Chunks:\n"
            f"{context}\n\n"
            "Anweisungen:\n"
            "1) Antworte ausschließlich mit Informationen aus den verfügbaren Chunks.\n"
            "2) Erfinde keine Fakten, Namen, Zahlen oder Zusammenhänge.\n"
            "3) Wenn die Chunks nicht ausreichen, sage klar: 'Dazu enthalten die bereitgestellten Chunks keine verlässliche Information.'\n"
            "4) Formuliere die Antwort kurz und klar auf Deutsch."
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du bist ein strikt quellgebundener Assistent. "
                        "Du darfst nur Informationen aus den gelieferten Chunks verwenden "
                        "und bei fehlender Evidenz keine Vermutungen äußern."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""
