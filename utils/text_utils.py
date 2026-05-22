import re


def count_chinese_chars(text: str) -> int:
    """Count the number of Chinese characters in a string."""
    return len(re.findall(r"[一-鿿]", text))


def estimate_tokens(text: str) -> int:
    """Rough token estimation for Chinese text (~1.5 tokens per char)."""
    chinese_chars = count_chinese_chars(text)
    non_chinese = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + non_chinese * 0.25)


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    """Truncate text to approximately fit within a token limit."""
    estimated = estimate_tokens(text)
    if estimated <= max_tokens:
        return text
    # Rough truncation: keep ratio of chinese/non-chinese
    ratio = max_tokens / estimated
    truncate_at = int(len(text) * ratio)
    return text[:truncate_at]


def format_conversation_for_prompt(messages: list) -> str:
    """Format chat messages into a readable conversation string."""
    lines = []
    for msg in messages:
        speaker = "销售" if msg.role == "user" else "客户"
        lines.append(f"{speaker}：{msg.content}")
    return "\n".join(lines)
