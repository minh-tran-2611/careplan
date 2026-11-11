from memory.short_term.buffer import ConversationBuffer

def build_memory(messages, max_turns: int = 6):
    buffer = ConversationBuffer(max_turns)
    for m in messages: buffer.add(m.role, m.content)
    return buffer
