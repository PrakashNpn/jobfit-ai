import pytest

from app.ingest import UnsupportedFileError, extract_text, split_into_chunks


def test_extract_text_markdown():
    assert extract_text("notes.md", b"# Title\nBody") == "# Title\nBody"


def test_extract_text_rejects_other_types():
    with pytest.raises(UnsupportedFileError):
        extract_text("sheet.xlsx", b"data")


def test_split_keeps_metadata_and_order():
    chunks = split_into_chunks("word " * 1000, source="cv.md", doc_type="resume")
    assert len(chunks) > 1
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert {c.source for c in chunks} == {"cv.md"}


def test_split_ignores_empty_text():
    assert split_into_chunks("   \n  ", source="empty.md", doc_type="other") == []
