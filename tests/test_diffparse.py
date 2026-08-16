import pytest

from app.core.diffparse import DiffParseError, parse_unified_diff

GIT_STYLE_DIFF = """\
diff --git a/src/db.ts b/src/db.ts
index 1111111..2222222 100644
--- a/src/db.ts
+++ b/src/db.ts
@@ -10,6 +10,9 @@ function run() {
 context line one
-old line removed
+added line one
+added line two
 context line two
+added line three
 trailing context
diff --git a/src/util.ts b/src/util.ts
index 3333333..4444444 100644
--- a/src/util.ts
+++ b/src/util.ts
@@ -1,2 +1,3 @@
 first line
+util added line
 second line
"""

BARE_UNIFIED_DIFF = """\
--- a/lib/foo.py
+++ b/lib/foo.py
@@ -1,3 +1,4 @@
 def foo():
+    print("hi")
     return 1

"""

DELETION_DIFF = """\
diff --git a/old.py b/old.py
deleted file mode 100644
index 1111111..0000000
--- a/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-line one
-line two
"""


def test_git_style_diff_line_numbers():
    parsed = parse_unified_diff(GIT_STYLE_DIFF)
    assert [f.path for f in parsed.files] == ["src/db.ts", "src/util.ts"]

    db_file = parsed.files[0]
    assert [(a.line_no, a.text) for a in db_file.added_lines] == [
        (11, "added line one"),
        (12, "added line two"),
        (14, "added line three"),
    ]

    util_file = parsed.files[1]
    assert [(a.line_no, a.text) for a in util_file.added_lines] == [
        (2, "util added line"),
    ]


def test_bare_unified_diff_without_git_header():
    parsed = parse_unified_diff(BARE_UNIFIED_DIFF)
    assert len(parsed.files) == 1
    assert parsed.files[0].path == "lib/foo.py"
    assert [(a.line_no, a.text) for a in parsed.files[0].added_lines] == [
        (2, '    print("hi")'),
    ]


def test_deletion_only_diff_has_no_added_lines():
    parsed = parse_unified_diff(DELETION_DIFF)
    assert len(parsed.files) == 1
    assert parsed.files[0].path == "old.py"
    assert parsed.files[0].added_lines == []


@pytest.mark.parametrize("garbage", ["", "hello world", "{\"not\": \"a diff\"}", "just some\nplain text\nno markers"])
def test_garbage_input_raises(garbage):
    with pytest.raises(DiffParseError):
        parse_unified_diff(garbage)
