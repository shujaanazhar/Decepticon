"""LLM decision layer — uses local Ollama to decide what (if anything) to say."""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
BOT_PERSONA = os.getenv(
    "BOT_PERSONA",
    "You are attending this Google Meet on behalf of the user. "
    "Be concise. Only respond when directly addressed or when you have something important to contribute. "
    "Keep responses under 3 sentences. "
    "If you don't need to say anything, reply with exactly: <SILENT>",
)


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
