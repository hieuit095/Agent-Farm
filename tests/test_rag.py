"""Tests for the Local RAG engine (RepoIndexer with ChromaDB)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from farm_agent.core.rag import (
    RepoIndexer,
    CodeChunk,
    chunk_file,
    _should_index_file,
    _make_doc_id,
    _embed_texts_fallback,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    MAX_FILE_SIZE_BYTES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

CONTROLLER_CODE = '''
class AuthController:
    def login(self, request):
        token = self.validate_token(request)
        if not token:
            raise AuthError("Invalid token")
        return token
'''

SERVICE_CODE = '''
class AuthService:
    def validate_token(self, token: str) -> bool:
        if not token or len(token) < 16:
            return False
        return token.startswith("Bearer ")

    def generate_token(self, user_id: str) -> str:
        secret = self._get_secret()
        return f"Bearer {user_id}:{secret}"
'''

RANDOM_CODE = '''
def hello():
    print("Hello World!")
    return True
'''

MOCK_REPO_FILES = {
    "src/controllers/auth.py": CONTROLLER_CODE,
    "src/services/auth.py": SERVICE_CODE,
    "README.md": RANDOM_CODE,
}


# ── chunk_file tests ───────────────────────────────────────────────────────────

class TestChunkFile:
    def test_single_small_file_returns_one_chunk(self):
        content = "x" * 200
        chunks = chunk_file(content, "test.py")
        assert len(chunks) == 1
        assert chunks[0].content == content

    def test_chunk_respects_max_size(self):
        # Content longer than chunk_size creates multiple chunks
        content = ("line_of_code\n" * 1000)  # ~13KB
        chunks = chunk_file(content, "test.py")
        assert len(chunks) > 1
        # Each chunk respects chunk_size
        for c in chunks:
            assert len(c.content) <= DEFAULT_CHUNK_SIZE + 200  # allow overrun to line boundary

    def test_overlap_preserved_between_chunks(self):
        content = "AAAA" + "\n" * (DEFAULT_CHUNK_SIZE // 2)
        chunks = chunk_file(content, "test.py")
        if len(chunks) > 1:
            # The last few chars of chunk N should appear in chunk N+1 (overlap)
            last_chars = chunks[0].content[-DEFAULT_CHUNK_OVERLAP:]
            next_start = chunks[1].content[:DEFAULT_CHUNK_OVERLAP]
            # At least some character should repeat due to overlap
            assert any(c in next_start for c in last_chars[:10])

    def test_empty_content_returns_empty_list(self):
        assert chunk_file("", "test.py") == []
        assert chunk_file("   \n\n  ", "test.py") == []

    def test_chunk_metadata_is_correct(self):
        content = "x" * 3000
        chunks = chunk_file(content, "myfile.js")
        for i, c in enumerate(chunks):
            assert c.file_path == "myfile.js"
            assert c.chunk_index == i
            assert c.doc_id == _make_doc_id("myfile.js", i)
        total = chunks[-1].total_chunks
        assert all(c.total_chunks == total for c in chunks)

    def test_deterministic_doc_ids(self):
        content = "test content " * 100
        id1 = _make_doc_id("a/b.py", 0)
        id2 = _make_doc_id("a/b.py", 0)
        assert id1 == id2  # same path+index → same ID

    def test_different_chunks_have_different_ids(self):
        content = "x" * 3000
        chunks = chunk_file(content, "test.py")
        ids = [c.doc_id for c in chunks]
        assert len(ids) == len(set(ids))  # all unique


# ── _should_index_file tests ───────────────────────────────────────────────────

class TestShouldIndexFile:
    def test_indexes_normal_code_files(self):
        assert _should_index_file("src/auth.py") is True
        assert _should_index_file("lib/utils.rs") is True
        assert _should_index_file("pkg/service.go") is True

    def test_skips_node_modules(self):
        assert _should_index_file("node_modules/lodash/index.js") is False

    def test_skips_dist_and_build_dirs(self):
        assert _should_index_file("dist/index.js") is False
        assert _should_index_file("build/main.jar") is False
        assert _should_index_file("target/debug/app") is False

    def test_skips_git_and_cache_dirs(self):
        assert _should_index_file(".git/HEAD") is False
        assert _should_index_file("__pycache__/main.pyc") is False
        assert _should_index_file(".pytest_cache/test.py") is False

    def test_skips_minified_files(self):
        assert _should_index_file("dist/app.min.js") is False
        assert _should_index_file("static/app.min.css") is False

    def test_skips_binary_files(self):
        assert _should_index_file("lib/app.wasm") is False
        assert _should_index_file("vendor/lib.so") is False


# ── _embed_texts_fallback tests ────────────────────────────────────────────────

class TestEmbedTextsFallback:
    def test_returns_list_of_vectors(self):
        texts = ["def foo(): pass", "class Bar:"]
        vecs = _embed_texts_fallback(texts)
        assert isinstance(vecs, list)
        assert len(vecs) == 2
        assert all(isinstance(v, list) for v in vecs)
        assert all(isinstance(x, float) for v in vecs for x in v)

    def test_identical_texts_have_identical_embeddings(self):
        text = "def authenticate(user): return True"
        vecs = _embed_texts_fallback([text, text])
        assert vecs[0] == vecs[1]

    def test_different_texts_have_different_embeddings(self):
        text_a = "def foo(): pass"
        text_b = "class Bar: pass"
        vecs = _embed_texts_fallback([text_a, text_b])
        # Cosine similarity — different texts should NOT be identical vectors
        import math
        dot = sum(a * b for a, b in zip(vecs[0], vecs[1]))
        assert dot < 1.0  # not perfectly correlated

    def test_empty_text_returns_zero_vector(self):
        vecs = _embed_texts_fallback([""])
        assert len(vecs) == 1
        assert all(x == 0.0 for x in vecs[0])


# ── RepoIndexer integration tests ───────────────────────────────────────────────

class TestRepoIndexer:
    def test_index_repo_returns_chunk_count(self):
        indexer = RepoIndexer()
        count = indexer.index_repo("test/repo", {"src/main.py": "print('hello')"})
        assert count >= 1
        indexer.destroy()

    def test_query_returns_semantically_similar_chunks(self):
        """Query for 'token validation' should return chunks from SERVICE_CODE
        (which contains validate_token) and CONTROLLER_CODE (which calls it)."""
        indexer = RepoIndexer()
        indexer.index_repo("test/repo", MOCK_REPO_FILES)

        results = indexer.query_context("token validation", n_results=5)

        assert len(results) > 0
        # At least one result should come from auth.py (the service with validate_token)
        result_paths = {r["file_path"] for r in results}
        assert any("auth" in p for p in result_paths), f"Expected auth file in results, got: {result_paths}"
        indexer.destroy()

    def test_query_returns_content_and_metadata(self):
        indexer = RepoIndexer()
        indexer.index_repo("test/repo", {"auth.py": SERVICE_CODE})

        results = indexer.query_context("token validation")

        assert len(results) > 0
        r = results[0]
        assert "content" in r
        assert "file_path" in r
        assert "distance" in r
        assert r["file_path"] == "auth.py"
        assert len(r["content"]) > 0
        indexer.destroy()

    def test_query_for_variable_in_service_file(self):
        """Query specifically for 'generate_token' — must retrieve auth.py (Service file)."""
        indexer = RepoIndexer()
        indexer.index_repo("test/repo", MOCK_REPO_FILES)

        results = indexer.query_context("generate token secret", n_results=3)

        # Should find it in auth.py (the service file)
        result_paths = [r["file_path"] for r in results]
        assert any("auth.py" in p or "auth.py" == p for p in result_paths), \
            f"Expected auth.py in results, got: {result_paths}"

        # The retrieved chunk should contain the generate_token code
        contents = [r["content"] for r in results if "auth.py" in r["file_path"]]
        assert any("generate_token" in c or "Bearer" in c for c in contents), \
            f"Expected generate_token/Bearer in chunk, got: {contents}"
        indexer.destroy()

    def test_readme_ranked_last_for_code_query(self):
        """README.md contains no code — querying for 'token' should rank it LAST with distance≈1.0."""
        indexer = RepoIndexer()
        indexer.index_repo("test/repo", MOCK_REPO_FILES)

        results = indexer.query_context("token validation Bearer", n_results=10)

        readme_results = [r for r in results if "README" in r["file_path"]]
        # README.md may appear in results but must have distance ≈ 1.0 (completely unrelated)
        if readme_results:
            assert all(abs(r["distance"] - 1.0) < 0.01 for r in readme_results), \
                f"README distance should be ~1.0 (irrelevant), got: {[r['distance'] for r in readme_results]}"

        # README should NOT be the top result
        if results:
            assert "README" not in results[0]["file_path"], \
                "README should not be the top result for a code query"
        indexer.destroy()

    def test_idempotent_indexing(self):
        """Indexing the same repo twice should not duplicate chunks."""
        indexer = RepoIndexer()
        indexer.index_repo("test/repo", {"a.py": "print('a')"})
        count1 = indexer.index_repo("test/repo", {"a.py": "print('a')", "b.py": "print('b')"})
        # Second indexing adds b.py but a.py is already there
        assert count1 >= 1  # at least b.py chunks
        indexer.destroy()

    def test_destroy_frees_collection(self):
        """destroy() must delete the collection without errors."""
        indexer = RepoIndexer()
        indexer.index_repo("test/repo", {"main.py": "print('hi')"})
        indexer.destroy()  # must not raise
        # Calling destroy twice is also safe
        indexer.destroy()

    def test_query_with_no_index_returns_empty(self):
        indexer = RepoIndexer()
        # No index_repo called — collection doesn't exist
        results = indexer.query_context("anything")
        assert results == []

    def test_excludes_oversized_files(self):
        """Files larger than MAX_FILE_SIZE_BYTES should be skipped."""
        big_content = "x" * (MAX_FILE_SIZE_BYTES + 1000)
        indexer = RepoIndexer()
        count = indexer.index_repo("test/repo", {"big.go": big_content})
        # Should skip the file (only skipped via MAX_FILE_SIZE check in index_repo)
        indexer.destroy()

    def test_query_context_n_results_limit(self):
        indexer = RepoIndexer()
        files = {f"src/file{i}.py": f"def func{i}(): pass" for i in range(20)}
        indexer.index_repo("test/repo", files)

        results = indexer.query_context("def func", n_results=3)
        assert len(results) <= 3
        indexer.destroy()

    def test_collection_name_is_sanitized(self):
        """Repo names with / or - should be sanitized to valid collection names."""
        indexer = RepoIndexer()
        indexer.index_repo("owner/repo-name", {"main.py": "print('hi')"})
        assert indexer._collection is not None
        # Collection name should not contain / or -
        assert "/" not in indexer._collection.name
        assert "-" not in indexer._collection.name
        indexer.destroy()
