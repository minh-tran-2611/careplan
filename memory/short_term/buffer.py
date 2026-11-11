from collections import deque

class ConversationBuffer:
    def __init__(self, max_turns: int = 6): self.messages = deque(maxlen=max_turns)
    def add(self, role: str, content: str):
        if role not in {"user", "assistant"}: raise ValueError("Unsupported role")
        self.messages.append({"role":role, "content":content[:3000]})
    def snapshot(self): return list(self.messages)
    def clear(self): self.messages.clear()
