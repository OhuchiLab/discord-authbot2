"""
[単体] utils.validators のテスト
"""

import pytest

from utils import (
    is_valid_email,
    is_valid_student_number,
    normalize_email,
    normalize_input,
    normalize_name,
    normalize_student_number,
)


@pytest.mark.parametrize(
    ("student_number", "expected"),
    [
        ("12345678", True),
        ("AB123456", True),
        ("ａｂ１２３４５６", True),  # 全角でも可
        (" 12345678 ", True),  # 前後の空白は無視
        ("1234567", False),  # 7 文字
        ("123456789", False),  # 9 文字
        ("1234-567", False),  # 記号
    ],
)
def test_学籍番号は英数字8文字(student_number, expected):
    assert is_valid_student_number(student_number) is expected


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("yamada.taro.21@shizuoka.ac.jp", True),
        ("YAMADA@SHIZUOKA.AC.JP", True),
        ("yamada@gmail.com", False),
        ("yamada@evil.shizuoka.ac.jp", False),  # サブドメインは不可
        ("yamada@shizuoka.ac.jp.evil.com", False),
        ("@shizuoka.ac.jp", False),
        ("yamada shizuoka.ac.jp", False),
        ("a b@shizuoka.ac.jp", False),
    ],
)
def test_メールアドレスは許可ドメインのみ(email, expected):
    assert is_valid_email(email, "shizuoka.ac.jp") is expected


def test_入力はNFKC正規化して前後の空白を除く():
    assert normalize_input("　ＡＢ１２　") == "AB12"


def test_氏名は空白をすべて除いて比較する():
    assert normalize_name("山田 太郎") == normalize_name("山田　太郎") == normalize_name("山田太郎")


def test_学籍番号は大文字_メールアドレスは小文字にそろえる():
    assert normalize_student_number("ab123456") == "AB123456"
    assert normalize_email("Yamada@Shizuoka.ac.jp") == "yamada@shizuoka.ac.jp"
