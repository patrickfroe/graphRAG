from openai import OpenAI

from app.config import get_settings


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_chat_model
        self.client = OpenAI(api_key=settings.openai_api_key)

    def answer(self, query: str, context_chunks: list[str]) -> str:
        context = "\n\n".join(context_chunks) if context_chunks else "Kein Kontext gefunden."
        prompt = (
            "Du bist ein hilfreicher Assistent. Nutze den bereitgestellten Kontext für deine Antwort.\n"
            f"Kontext:\n{context}\n\n"
            f"Frage: {query}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Antworte präzise und ehrlich auf Deutsch."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
