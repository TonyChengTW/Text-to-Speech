import pytest
from tts import chunk_text


def test_chunk_short_text():
    """Test text shorter than chunk_size is not chunked."""
    text = "你好，歡迎使用。"
    chunks = chunk_text(text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_chinese_sentences():
    """Test chunking by Chinese sentence boundaries."""
    text = "第一句話。第二句話！第三句話？"
    chunks = chunk_text(text, chunk_size=10)
    assert len(chunks) == 3


def test_chunk_english_sentences():
    """Test chunking by English sentence boundaries."""
    text = "First sentence. Second sentence! Third sentence?"
    chunks = chunk_text(text, chunk_size=20)
    assert len(chunks) == 3


def test_chunk_mixed_text():
    """Test chunking mixed Chinese and English text."""
    text = "Hello world. 你好世界！Goodbye."
    chunks = chunk_text(text, chunk_size=15)
    assert len(chunks) == 3


def test_chunk_preserves_inline_tags():
    """Test chunking preserves inline tags."""
    text = "(开心)第一句。[笑]第二句！"
    chunks = chunk_text(text, chunk_size=10)
    assert "(开心)" in chunks[0]
    assert "[笑]" in chunks[1]
