"""
[単体] several_types.StudentInfo のテスト
"""

import dataclasses

import pytest

from several_types import Grade, StudentInfo

STUDENT = StudentInfo("uuid-1", "山田 太郎", "AB123456", "yamada@shizuoka.ac.jp", Grade.OBOG, "111")


def test_辞書に変換して元に戻せる():
    assert StudentInfo.from_dict(STUDENT.to_dict()) == STUDENT


def test_学年は値の文字列で保存する():
    assert STUDENT.to_dict()["grade"] == "OB/OG"


def test_discord_idが無い辞書は未認証として読み込む():
    data = STUDENT.to_dict()
    del data["discord_id"]
    assert StudentInfo.from_dict(data).discord_id is None


def test_値は変更できない():
    with pytest.raises(dataclasses.FrozenInstanceError):
        STUDENT.name = "別人"
