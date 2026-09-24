"""
ユーザーが入力した値の形式チェックと正規化を行う関数群

比較用の正規化では、まず NFKC 正規化で全角英数字を半角にそろえます。
(例: "ｍ１" → "m1"、全角空白 → 半角空白)
"""

import re
import unicodedata

_STUDENT_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9]{8}$")
_EMAIL_LOCAL_PART_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+$")


def normalize_input(text: str) -> str:
    """
    ユーザーの入力を NFKC 正規化し、前後の空白を取り除く

    Args:
        text (str): ユーザーの入力

    Returns:
        str: 正規化した文字列
    """
    return unicodedata.normalize("NFKC", text).strip()


def is_valid_student_number(student_number: str) -> bool:
    """
    学籍番号が「英数字 8 文字」の形式かどうかを判定する

    Args:
        student_number (str): 判定する学籍番号

    Returns:
        bool: 形式が正しければ True
    """
    return _STUDENT_NUMBER_PATTERN.fullmatch(normalize_input(student_number)) is not None


def is_valid_email(email: str, allowed_domain: str) -> bool:
    """
    メールアドレスが「許可されたドメインのアドレス」かどうかを判定する

    Args:
        email (str): 判定するメールアドレス
        allowed_domain (str): 許可するドメイン (例: "shizuoka.ac.jp")

    Returns:
        bool: `xxx@<allowed_domain>` の形式であれば True
    """
    local_part, at_mark, domain = normalize_input(email).rpartition("@")
    return (
        at_mark == "@"
        and _EMAIL_LOCAL_PART_PATTERN.fullmatch(local_part) is not None
        and domain.lower() == allowed_domain.lower()
    )


def normalize_name(name: str) -> str:
    """
    氏名を比較用に正規化する

    半角・全角の空白をすべて取り除きます。
    これにより "山田 太郎" と "山田　太郎" と "山田太郎" は同じ氏名として扱われます。

    Args:
        name (str): 氏名

    Returns:
        str: 空白を取り除いた氏名
    """
    return re.sub(r"\s+", "", normalize_input(name))


def normalize_student_number(student_number: str) -> str:
    """
    学籍番号を比較用に正規化する (大文字にそろえる)
    """
    return normalize_input(student_number).upper()


def normalize_email(email: str) -> str:
    """
    メールアドレスを比較用に正規化する (小文字にそろえる)
    """
    return normalize_input(email).lower()
