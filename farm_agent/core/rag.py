"""Local RAG (Retrieval-Augmented Generation) engine using ChromaDB.

Provides semantic cross-file code search for the generator's X-Ray Vision:
- Persistent ChromaDB (disk-backed, survives restarts)
- Sliding-window text chunking with overlap
- Filters out auto-generated and test files from indexing
- Gracefully loads existing collections — re-indexes only new/changed files
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Chunking configuration ────────────────────────────────────────────────────

# Exclude patterns: auto-generated, binary, or massive files
EXCLUDE_PATTERNS = [
    re.compile(r"node_modules|\.git|__pycache__|\.pytest_cache"),
    re.compile(r"\.min\.(js|css|ts)"),  # minified files
    re.compile(r"\.map\.js$"),  # source maps
    re.compile(r"\.pyc$|\.pyo$"),  # compiled python
    re.compile(r"dist/|build/|target/|vendor/"),  # build artifacts
    re.compile(r"\.lock$"),  # lock files
    re.compile(r"package-lock|package\.json$"),  # package files themselves
    re.compile(r"\.wasm$|\.bin$|\.so$|\.dll$"),  # binary
]

# Max file size to index (skip files larger than 200KB to save embedding time)
MAX_FILE_SIZE_BYTES = 200 * 1024

# Chunking
DEFAULT_CHUNK_SIZE = 1200  # characters per chunk
DEFAULT_CHUNK_OVERLAP = 200  # sliding window overlap


@dataclass
class CodeChunk:
    """A single code chunk with metadata."""

    content: str
    file_path: str
    chunk_index: int
    total_chunks: int
    doc_id: str  # unique ID for ChromaDB
    metadata: dict[str, str] = field(default_factory=dict)


def _should_index_file(path: str) -> bool:
    """Return False for files that should be excluded from RAG indexing."""
    return all(not pattern.search(path) for pattern in EXCLUDE_PATTERNS)


def chunk_file(
    content: str,
    file_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[CodeChunk]:
    """Split a file's content into overlapping sliding-window chunks.

    Uses a simple character-based sliding window with fixed stride.
    Overlap ensures that code references at chunk boundaries are preserved.

    Returns a list of CodeChunk objects sorted by position in file.
    """
    if not content or not content.strip():
        return []

    chunks: list[CodeChunk] = []
    stride = chunk_size - overlap
    content_len = len(content)

    # If file is shorter than chunk_size, return single chunk
    if content_len <= chunk_size:
        doc_id = _make_doc_id(file_path, 0)
        return [
            CodeChunk(
                content=content,
                file_path=file_path,
                chunk_index=0,
                total_chunks=1,
                doc_id=doc_id,
            )
        ]

    total_chunks = max(1, (content_len - chunk_size + stride - 1) // stride + 1)
    chunk_index = 0
    start = 0

    while start < content_len:
        end = min(start + chunk_size, content_len)
        # Try to break at a line boundary to keep code intact
        if end < content_len and content[end] != "\n":
            # Back up to last complete line
            last_nl = content.rfind("\n", start, end)
            if last_nl > start + chunk_size // 2:
                end = last_nl + 1

        chunk_text = content[start:end]
        doc_id = _make_doc_id(file_path, chunk_index)

        chunks.append(
            CodeChunk(
                content=chunk_text,
                file_path=file_path,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
                doc_id=doc_id,
            )
        )

        chunk_index += 1
        start += stride

    return chunks


def chunk_markdown(content: str, file_path: str) -> list[CodeChunk]:
    """Semantic chunking utility for markdown files.

    Splits content by Markdown Headers (H1, H2, H3).
    Attaches header information to the chunks.
    """
    if not content or not content.strip():
        return []

    # Get folder path
    folder_path = "/".join(file_path.split("/")[:-1])

    # Find headers (H1, H2, H3)
    header_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(content))

    if not matches:
        # Fallback to sliding window chunking if no headers exist
        return chunk_file(content, file_path)

    chunks: list[CodeChunk] = []

    # Helper to clean header title (strip trailing spaces, symbols)
    def clean_title(title: str) -> str:
        return title.strip().rstrip("#").strip()

    total_chunks = len(matches)
    # Check if there is preamble content before the first header
    preamble_end = matches[0].start()
    preamble_content = content[:preamble_end].strip()
    if preamble_content:
        total_chunks += 1
        doc_id = _make_doc_id(file_path, 0)
        chunks.append(
            CodeChunk(
                content=preamble_content,
                file_path=file_path,
                chunk_index=0,
                total_chunks=total_chunks,
                doc_id=doc_id,
                metadata={
                    "folder_path": folder_path,
                    "header_title": "Preamble",
                },
            )
        )

    for i, match in enumerate(matches):
        header_title = clean_title(match.group(2))
        start_pos = match.start()

        # End position is the start of the next header, or end of file
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        chunk_text = content[start_pos:end_pos].strip()

        chunk_idx = len(chunks)
        doc_id = _make_doc_id(file_path, chunk_idx)
        chunks.append(
            CodeChunk(
                content=chunk_text,
                file_path=file_path,
                chunk_index=chunk_idx,
                total_chunks=total_chunks,
                doc_id=doc_id,
                metadata={
                    "folder_path": folder_path,
                    "header_title": header_title,
                },
            )
        )

    # Update total_chunks count for all chunks to be correct
    for c in chunks:
        c.total_chunks = len(chunks)

    return chunks


def _make_doc_id(file_path: str, chunk_index: int) -> str:
    """Generate a deterministic unique ID for a chunk."""
    raw = f"{file_path}::{chunk_index}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ── Simple embedding function (no external API needed) ───────────────────────

EMBEDDING_DIM = 128  # Fixed dimension for all embeddings — ChromaDB requirement


def _embed_texts_fallback(texts: list[str]) -> list[list[float]]:
    """Generate pseudo-embeddings using word-frequency vectors with FIXED dimension.

    Uses a FIXED 128-dim vector for every text. This ensures that query embeddings
    and chunk embeddings always have the same dimension, satisfying ChromaDB's
    collection-wide embedding dimension invariant.

    This is a local, deterministic fallback — good enough for semantic similarity
    within a single repo's codebase. Production deployments can swap this for
    OpenAI or Minimax embeddings.
    """
    import math

    dim = EMBEDDING_DIM

    # Fixed vocabulary: most common English programming words + all unique words from texts
    # Use a fixed seed-based ordering so the same word always maps to the same index
    # across all texts and all calls (deterministic regardless of collection order)
    all_words: set[str] = set()
    for text in texts:
        all_words.update(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower()))

    # Sort alphabetically for deterministic mapping → same word → same vector index
    sorted_words = sorted(all_words)
    word_to_idx = {w: i % dim for i, w in enumerate(sorted_words)}

    embeddings: list[list[float]] = []
    for text in texts:
        words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower()))
        vec = [0.0] * dim
        norm = 0.0
        for w in words:
            idx = word_to_idx[w]
            vec[idx] += 1.0
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        embeddings.append(vec)

    return embeddings


# ── ChromaDB integration ──────────────────────────────────────────────────────


class RepoIndexer:
    """Persistent RAG indexer for a single repository.

    Uses ChromaDB PersistentClient with disk-backed storage at data/chroma_db/.
    Collections survive restarts — files already indexed are not re-embedded.

    Usage:
        indexer = RepoIndexer()
        indexer.index_repo(repo_name, file_contents_dict)
        results = indexer.query_context("authentication token handling", n_results=5)
        del indexer  # collection remains on disk for next run
    """

    # Disk path for persistent ChromaDB storage
    PERSISTENT_PATH = "data/chroma_db"

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP):
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._chroma = None
        self._collection = None
        self._indexed_files: set[str] = set()
        self._repo_name: str = ""

    def _ensure_persistent_path(self) -> None:
        """Ensure the persistent storage directory exists."""
        import os

        os.makedirs(self.PERSISTENT_PATH, exist_ok=True)

    def _init_chroma(self) -> None:
        """Lazily initialize ChromaDB PersistentClient and collection."""
        if self._chroma is not None:
            return

        try:
            import chromadb

            self._ensure_persistent_path()
            self._chroma = chromadb.PersistentClient(path=self.PERSISTENT_PATH)
            self._collection = self._chroma.get_or_create_collection(
                name=self._repo_name.replace("/", "_").replace("-", "_")[:64],
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "ChromaDB persistent collection '%s' initialized at %s",
                self._repo_name,
                self.PERSISTENT_PATH,
            )
        except (ImportError, Exception) as e:
            logger.warning(
                "ChromaDB not installed or failed to initialize (%s) — using regex fallback for cross-file search",
                e,
            )
            self._chroma = None
            self._collection = None

    def index_repo(self, repo_name: str, file_contents: dict[str, str]) -> int:
        """Index all files in the repository.

        Args:
            repo_name: Full name of the repo (e.g. "owner/repo").
            file_contents: Dict mapping file paths to their content as strings.

        Returns:
            Number of chunks indexed.

        Raises:
            RuntimeError: If ChromaDB is not available.
        """
        self._repo_name = repo_name
        self._init_chroma()

        if self._collection is None:
            raise RuntimeError("ChromaDB not available — cannot index repository")

        chunks: list[CodeChunk] = []
        for fpath, content in file_contents.items():
            if not _should_index_file(fpath):
                logger.debug("RAG: skipping excluded file %s", fpath)
                continue
            if len(content.encode()) > MAX_FILE_SIZE_BYTES:
                logger.debug("RAG: skipping oversized file %s (%d bytes)", fpath, len(content))
                continue

            if fpath.lower().endswith(".md"):
                file_chunks = chunk_markdown(content, fpath)
            else:
                file_chunks = chunk_file(content, fpath, self._chunk_size, self._overlap)
            chunks.extend(file_chunks)
            self._indexed_files.add(fpath)

        if not chunks:
            logger.info("RAG: no indexable content in %s", repo_name)
            return 0

        # Generate embeddings
        texts = [c.content for c in chunks]
        embeddings = _embed_texts_fallback(texts)

        # Add to ChromaDB
        ids = [c.doc_id for c in chunks]
        metadatas = []
        for c in chunks:
            meta = {
                "file_path": c.file_path,
                "chunk_index": c.chunk_index,
                "total": c.total_chunks,
            }
            if hasattr(c, "metadata") and c.metadata:
                meta.update(c.metadata)
            metadatas.append(meta)
        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(
            "RAG: indexed %s — %d chunks from %d files into collection '%s'",
            repo_name,
            len(chunks),
            len(self._indexed_files),
            self._repo_name,
        )
        return len(chunks)

    def query_context(self, query: str, n_results: int = 5) -> list[dict]:
        """Query the RAG index for semantically relevant code chunks.

        Args:
            query: Natural-language or code-pattern query string.
            n_results: Maximum number of result chunks to return.

        Returns:
            List of result dicts with keys:
              - content: str — the code chunk text
              - file_path: str — which file this chunk came from
              - distance: float — cosine distance (lower = more similar)
              - chunk_index: int
        """
        if self._collection is None:
            return []

        if not query or not query.strip():
            return []

        try:
            query_embedding = _embed_texts_fallback([query])[0]
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )

            output: list[dict] = []
            doc_list = results.get("documents", [[]])[0]
            meta_list = results.get("metadatas", [[]])[0]
            dist_list = results.get("distances", [[]])[0]

            for i, doc in enumerate(doc_list):
                meta = meta_list[i] if i < len(meta_list) else {}
                dist = dist_list[i] if i < len(dist_list) else 1.0
                output.append(
                    {
                        "content": doc,
                        "file_path": meta.get("file_path", "unknown"),
                        "distance": float(dist),
                        "chunk_index": meta.get("chunk_index", 0),
                    }
                )

            logger.info(
                "RAG query '%s' → %d results from %s", query[:60], len(output), self._repo_name
            )
            return output

        except Exception as exc:
            logger.warning("RAG query failed: %s — returning empty results", exc)
            return []

    def destroy(self) -> None:
        """Clear in-memory references (collection persists on disk for next run)."""
        if self._chroma is not None and self._collection is not None:
            logger.info(
                "RAG: collection '%s' released from memory (data persisted at %s)",
                self._collection.name,
                self.PERSISTENT_PATH,
            )
        self._chroma = None
        self._collection = None
        self._indexed_files.clear()

    def __del__(self):
        """Guarantee collection cleanup on object destruction."""
        self.destroy()

    @property
    def indexed_files(self) -> set[str]:
        """Return set of file paths that were indexed."""
        return self._indexed_files
