"""
[API] database パッケージの公開 I/F のテスト

学生情報ファイルの形式が、詳細設計書 (docs/detailed_design.md「学生情報ファイルの形式」) どおりであることを確認します。
ファイルの形式を変えると、既存の学生情報が読めなくなるためです。
"""

import msgpack

from database import DatabaseController
from several_types import Grade, StudentInfo

STUDENT = StudentInfo("uuid-1", "山田 太郎", "AB123456", "yamada@shizuoka.ac.jp", Grade.OBOG, "111")

DOCUMENTED_RECORD = {
    "uuid": "uuid-1",
    "name": "山田 太郎",
    "student_number": "AB123456",
    "email": "yamada@shizuoka.ac.jp",
    "grade": "OB/OG",
    "discord_id": "111",
}
"""詳細設計書に記載したレコードの形"""


def test_保存したファイルは設計書どおりの形式(tmp_path):
    filepath = tmp_path / "students.msgpack"
    DatabaseController(filepath).add(STUDENT)

    with open(filepath, "rb") as f:
        assert msgpack.unpack(f) == [DOCUMENTED_RECORD]


def test_設計書どおりの形式のファイルを読み込める(tmp_path):
    filepath = tmp_path / "students.msgpack"
    unauthenticated = {**DOCUMENTED_RECORD, "uuid": "uuid-2", "discord_id": None}
    with open(filepath, "wb") as f:
        msgpack.pack([DOCUMENTED_RECORD, unauthenticated], f)

    database = DatabaseController(filepath)

    assert database.find_by_discord_id("111") == STUDENT
    assert database.find_by_uuid("uuid-2").discord_id is None
