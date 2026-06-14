import re


FILLER_PATTERN = re.compile(r"\b(um+|uh+|erm+|ah+|like)\b", re.IGNORECASE)
WHITESPACE_PATTERN = re.compile(r"[ \t]+")
BLANK_LINES_PATTERN = re.compile(r"\n{3,}")


def normalize_transcript(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = FILLER_PATTERN.sub("", text)
    text = WHITESPACE_PATTERN.sub(" ", text)
    text = BLANK_LINES_PATTERN.sub("\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if current_len + len(paragraph) + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        if len(paragraph) > max_chars:
            for i in range(0, len(paragraph), max_chars):
                part = paragraph[i : i + max_chars].strip()
                if part:
                    chunks.append(part)
            continue
        current.append(paragraph)
        current_len += len(paragraph) + 2

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def fit_for_prompt(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    head_size = max_chars // 3
    tail_size = max_chars // 3
    middle_size = max_chars - head_size - tail_size - 220
    middle_start = max((len(text) // 2) - (middle_size // 2), 0)
    middle_end = middle_start + middle_size
    return (
        "[Transcript beginning]\n"
        f"{text[:head_size]}\n\n"
        "[Transcript middle excerpt]\n"
        f"{text[middle_start:middle_end]}\n\n"
        "[Transcript ending]\n"
        f"{text[-tail_size:]}\n\n"
        "[Note: transcript was shortened for model context while the full transcript is stored in the database.]"
    )


def clean_list(values: object, max_items: int = 12) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for item in values:
        text = str(item).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned[:max_items]

