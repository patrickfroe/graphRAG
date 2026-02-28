import unittest

from graphrag.chat import ChatService


class TestChatService(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ChatService()

    def test_generate_reply_for_empty_message(self) -> None:
        self.assertEqual(
            self.service.generate_reply("   "),
            "Please provide a message so I can help.",
        )

    def test_stream_matches_full_reply(self) -> None:
        message = "What is graph retrieval?"
        full = self.service.generate_reply(message)
        streamed = "".join(self.service.stream_reply(message)).strip()
        self.assertEqual(streamed, full)


if __name__ == "__main__":
    unittest.main()
