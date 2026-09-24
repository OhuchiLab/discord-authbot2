"""
[API] database パッケージの公開 I/F のテスト

学生情報ファイルの形式が、詳細設計書 (docs/detailed_design.md「学生情報ファイルの形式」) どおりであることを確認します。
ファイルの形式を変えると、既存の学生情報が読めなくなるためです。
"""

import dataclasses

import msgpack
import pytest

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
"""詳細設計書に記載した学生情報 1 件の形"""


def read_file(filepath) -> object:
    with open(filepath, "rb") as f:
        return msgpack.unpack(f)


def write_file(filepath, data) -> None:
    with open(filepath, "wb") as f:
        msgpack.pack(data, f)


def test_保存したファイルは設計書どおりの形式(tmp_path):
    filepath = tmp_path / "students.msgpack"
    DatabaseController(filepath).add(STUDENT)

    assert read_file(filepath) == {
        "format_version": 2,
        "students": [DOCUMENTED_RECORD],
        "completed_fiscal_years": [],
    }


def test_設計書どおりの形式のファイルを読み込める(tmp_path):
    filepath = tmp_path / "students.msgpack"
    unauthenticated = {**DOCUMENTED_RECORD, "uuid": "uuid-2", "discord_id": None}
    write_file(
        filepath,
        {"format_version": 2, "students": [DOCUMENTED_RECORD, unauthenticated], "completed_fiscal_years": [2027]},
    )

    database = DatabaseController(filepath)

    assert database.find_by_discord_id("111") == STUDENT
    assert database.find_by_uuid("uuid-2").discord_id is None
    assert database.completed_fiscal_years() == {2027}


def test_以前の形式_学生情報の配列だけ_のファイルも読み込める(tmp_path):
    filepath = tmp_path / "students.msgpack"
    write_file(filepath, [DOCUMENTED_RECORD])

    database = DatabaseController(filepath)

    assert database.get_all() == [STUDENT]
    assert database.completed_fiscal_years() == set()


def test_年度更新は学生情報と実行済み年度をまとめて保存する(tmp_path):
    filepath = tmp_path / "students.msgpack"
    student = dataclasses.replace(STUDENT, grade=Grade.B4)
    DatabaseController(filepath).add(student)

    DatabaseController(filepath).commit_year_update([dataclasses.replace(student, grade=Grade.M1)], 2027)

    saved = read_file(filepath)
    assert saved["students"][0]["grade"] == "M1"
    assert saved["completed_fiscal_years"] == [2027]


def test_実行済みの年度で年度更新するとエラーになり_何も保存しない(tmp_path):
    filepath = tmp_path / "students.msgpack"
    database = DatabaseController(filepath)
    database.add(dataclasses.replace(STUDENT, grade=Grade.B4))
    database.commit_year_update([], 2027)

    with pytest.raises(ValueError):
        database.commit_year_update([dataclasses.replace(STUDENT, grade=Grade.M1)], 2027)

    assert DatabaseController(filepath).find_by_uuid("uuid-1").grade == Grade.B4
