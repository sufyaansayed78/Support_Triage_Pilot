"""Markdown-aware chunker shared by the ingestion script and the local retriever (pure Python)."""


def chunk_markdown(text: str, max_chars: int = 800) -> list[str]:
    """Group paragraphs up to max_chars, prefixing each chunk with its nearest heading."""
    heading, buf, chunks = "", [], []

    def flush() -> None:
        if buf:
            body = "\n\n".join(buf).strip()
            chunks.append(f"{heading}\n{body}".strip() if heading else body)
            buf.clear()

    for para in (p.strip() for p in text.replace("\r\n", "\n").split("\n\n")):
        if not para:
            continue
        if para.startswith("#"):
            flush()
            heading = para.splitlines()[0].lstrip("# ").strip()
            para = "\n".join(para.splitlines()[1:]).strip()
            if not para:
                continue
        if buf and sum(map(len, buf)) + len(para) > max_chars:
            flush()
        buf.append(para)
    flush()
    return chunks
