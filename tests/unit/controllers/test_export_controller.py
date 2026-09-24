"""
[単体] controllers.ExportController (学生情報の書き出し) のテスト

データベースは偽物 (InMemoryDatabase) に置き換えています。
"""

import csv
import io
from datetime import date

import msgpack
import pytest

from controllers import ExportController
from several_types import Grade, StudentInfo
from tests.fakes import InMemoryDatabase

YAMADA = StudentInfo("uuid-1", "山田 太郎", "AB123456", "yamada@shizuoka.ac.jp", Grade.M1, "101")
SUZUKI = StudentInfo("uuid-2", "鈴木, 花子", "CD123456", "suzuki@shizuoka.ac.jp", Grade.OBOG)


@pytest.fixture
def controller() -> ExportController:
    return ExportController(InMemoryDatabase([SUZUKI, YAMADA]), today=lambda: date(2027, 3, 1))


def test_CSVは見出し付きで学年順に並べ_BOM付きUTF8にする(controller):
    exported = controller.export_csv()

    assert exported.filename == "students-20270301.csv"
    assert exported.data.startswith("﻿".encode())
    rows = list(csv.reader(io.StringIO(exported.data.decode("utf-8-sig"))))
    assert rows == [
        ["氏名", "学籍番号", "学年", "メールアドレス", "Discord ID", "uuid"],
        ["山田 太郎", "AB123456", "M1", "yamada@shizuoka.ac.jp", "101", "uuid-1"],
        ["鈴木, 花子", "CD123456", "OB/OG", "suzuki@shizuoka.ac.jp", "", "uuid-2"],  # カンマを含んでも崩れない
    ]
    assert exported.student_count == 2


def test_msgpackはデータベースのファイルと同じ内容(controller):
    exported = controller.export_msgpack()

    assert exported.filename == "students-20270301.msgpack"
    assert [s["uuid"] for s in msgpack.unpackb(exported.data)["students"]] == ["uuid-2", "uuid-1"]
    assert exported.student_count == 2
