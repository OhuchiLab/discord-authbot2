"""
[単体] several_types.Grade のテスト
"""

import pytest

from several_types import Grade


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("B4", Grade.B4),
        (" m1 ", Grade.M1),
        ("OB/OG", Grade.OBOG),
        ("obog", Grade.OBOG),
        ("teacher", Grade.TEACHER),
        ("B5", None),
        ("", None),
    ],
)
def test_入力文字列を学年に変換できる(text, expected):
    assert Grade.parse(text) == expected
