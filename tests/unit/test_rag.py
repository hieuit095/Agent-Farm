import sys
from unittest.mock import MagicMock

# Mock chromadb module before importing it anywhere
mock_chromadb = MagicMock()
sys.modules["chromadb"] = mock_chromadb

from unittest.mock import MagicMock, patch

from farm_agent.core.rag import RepoIndexer, chunk_markdown


def test_chunk_markdown_basic():
    markdown_content = """# Subsystem A
This is subsystem A documentation.

## Subsystem A Detail
Here is more detail.

# Subsystem B
This is subsystem B documentation.
"""
    file_path = "docs/architecture/subsystem_a.md"
    chunks = chunk_markdown(markdown_content, file_path)

    # We expect 3 chunks: H1 (Subsystem A), H2 (Subsystem A Detail), H1 (Subsystem B)
    assert len(chunks) == 3

    # Check folder path metadata
    assert all(c.metadata["folder_path"] == "docs/architecture" for c in chunks)

    # Check header title metadata
    assert chunks[0].metadata["header_title"] == "Subsystem A"
    assert chunks[1].metadata["header_title"] == "Subsystem A Detail"
    assert chunks[2].metadata["header_title"] == "Subsystem B"

    # Check contents
    assert "# Subsystem A" in chunks[0].content
    assert "## Subsystem A Detail" in chunks[1].content
    assert "# Subsystem B" in chunks[2].content


def test_chunk_markdown_with_preamble():
    markdown_content = """Preamble content before headers.
    
# Subsystem A
This is subsystem A.
"""
    file_path = "docs/subsystem.md"
    chunks = chunk_markdown(markdown_content, file_path)

    # Expect 2 chunks: preamble + header
    assert len(chunks) == 2
    assert chunks[0].metadata["header_title"] == "Preamble"
    assert "Preamble content" in chunks[0].content

    assert chunks[1].metadata["header_title"] == "Subsystem A"
    assert "# Subsystem A" in chunks[1].content


def test_chunk_markdown_fallback():
    # Test fallback to sliding window chunking when no headers are present
    content = (
        "Some document that doesn't have any markdown headers. It just has normal paragraph text."
    )
    file_path = "docs/plain.md"

    chunks = chunk_markdown(content, file_path)
    assert len(chunks) == 1
    assert chunks[0].file_path == file_path


@patch("chromadb.PersistentClient")
def test_repo_indexer_metadata(mock_persistent_client):
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_persistent_client.return_value = mock_client
    mock_client.get_or_create_collection.return_value = mock_collection

    indexer = RepoIndexer()

    file_contents = {
        "docs/subsystem_a.md": "# Subsystem A\nContent description.",
        "src/main.py": "def main():\n    pass",
    }

    indexer.index_repo("test/repo", file_contents)

    # Verify get_or_create_collection was called
    mock_client.get_or_create_collection.assert_called_once()

    # Verify collection.add was called
    mock_collection.add.assert_called_once()
    kwargs = mock_collection.add.call_args[1]

    # Verify metadata contains custom fields for the markdown file
    metadatas = kwargs["metadatas"]

    md_meta = [m for m in metadatas if m["file_path"] == "docs/subsystem_a.md"]
    assert len(md_meta) > 0
    assert md_meta[0]["header_title"] == "Subsystem A"
    assert md_meta[0]["folder_path"] == "docs"

    py_meta = [m for m in metadatas if m["file_path"] == "src/main.py"]
    assert len(py_meta) > 0
    # Python file won't have markdown header_title
    assert "header_title" not in py_meta[0]
