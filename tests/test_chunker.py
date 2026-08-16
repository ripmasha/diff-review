from app.core.chunker import chunk_diff
from app.core.diffparse import FileDiff, ParsedDiff


def make_file(path: str, size: int) -> FileDiff:
    return FileDiff(path=path, raw_text="x" * size, added_lines=[])


def test_small_files_pack_into_one_chunk():
    parsed = ParsedDiff(files=[make_file("a.py", 20), make_file("b.py", 20)])
    chunks = chunk_diff(parsed, chunk_bytes=100)
    assert len(chunks) == 1
    assert [f.path for f in chunks[0].files] == ["a.py", "b.py"]


def test_files_split_across_chunks_on_boundary():
    # 20 + 30 fits in 64, but +25 does not -> [a,b], [c]
    parsed = ParsedDiff(
        files=[
            make_file("a.py", 20),
            make_file("b.py", 30),
            make_file("c.py", 25),
        ]
    )
    chunks = chunk_diff(parsed, chunk_bytes=64)
    assert len(chunks) == 2
    assert [f.path for f in chunks[0].files] == ["a.py", "b.py"]
    assert [f.path for f in chunks[1].files] == ["c.py"]


def test_no_file_spans_two_chunks():
    parsed = ParsedDiff(
        files=[
            make_file("a.py", 40),
            make_file("b.py", 40),
        ]
    )
    chunks = chunk_diff(parsed, chunk_bytes=64)
    all_paths = [f.path for chunk in chunks for f in chunk.files]
    assert all_paths == ["a.py", "b.py"]
    for chunk in chunks:
        assert len(chunk.files) <= 2


def test_oversized_single_file_is_its_own_chunk():
    parsed = ParsedDiff(
        files=[
            make_file("a.py", 10),
            make_file("huge.py", 200),
            make_file("b.py", 10),
        ]
    )
    chunks = chunk_diff(parsed, chunk_bytes=64)
    assert len(chunks) == 3
    assert [f.path for f in chunks[0].files] == ["a.py"]
    assert [f.path for f in chunks[1].files] == ["huge.py"]
    assert [f.path for f in chunks[2].files] == ["b.py"]
