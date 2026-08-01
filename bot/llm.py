"""LLM decision layer — uses local Ollama to decide what (if anything) to say."""

import requests

import config

OLLAMA_HOST = config.OLLAMA_HOST
OLLAMA_MODEL = config.OLLAMA_MODEL
BOT_PERSONA = config.BOT_PERSONA


class ConversationMemory:
    def __init__(self, max_turns=20):
        self.max_turns = max_turns
        self.history = []

    def add(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-self.max_turns * 2:]

    def get_messages(self):
        return [{"role": "system", "content": BOT_PERSONA}] + self.history


memory = ConversationMemory()


def should_respond(transcript: str) -> tuple[bool, str]:
    """
    Given what was just said in the meeting, decide if the bot should speak.
    Returns (should_speak, response_text).
    """
    memory.add("user", f"[Meeting transcript]: {transcript}")

    payload = {
        "model": OLLAMA_MODEL,
        "messages": memory.get_messages(),
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 150,
        },
    }

    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        reply = data["message"]["content"].strip()
    except Exception as e:
        print(f"[llm] Error: {e}")
        return False, ""

    if not reply or "<silent>" in reply.lower():
        memory.add("assistant", "<SILENT>")
        return False, ""

    memory.add("assistant", reply)
    return True, reply


def reset_memory():
    memory.history.clear()
