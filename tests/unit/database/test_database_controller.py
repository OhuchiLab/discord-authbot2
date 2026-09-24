"""
[単体] database.DatabaseController のテスト (一時フォルダの実ファイルを使用)
"""

import dataclasses

import pytest

from database import DatabaseController
from several_types import Grade, StudentInfo


def make_student(uuid: str = "uuid-1") -> StudentInfo:
    return StudentInfo(
        uuid=uuid,
        name="山田 太郎",
        student_number="12345678",
        email="yamada.taro.21@shizuoka.ac.jp",
        grade=Grade.M1,
    )


def test_ファイルが無ければ空のデータベースになる(tmp_path):
    database = DatabaseController(tmp_path / "students.msgpack")
    assert database.get_all() == []


def test_追加した学生情報は再起動後も読み込める(tmp_path):
    filepath = tmp_path / "sub" / "students.msgpack"
    DatabaseController(filepath).add(make_student())

    reloaded = DatabaseController(filepath)
    assert reloaded.get_all() == [make_student()]


def test_更新した学生情報は再起動後も読み込める(tmp_path):
    filepath = tmp_path / "students.msgpack"
    database = DatabaseController(filepath)
    database.add(make_student())
    database.update(dataclasses.replace(make_student(), discord_id="999"))

    reloaded = DatabaseController(filepath)
    assert reloaded.find_by_discord_id("999") == dataclasses.replace(make_student(), discord_id="999")


def test_同じuuidは追加できない(tmp_path):
    database = DatabaseController(tmp_path / "students.msgpack")
    database.add(make_student())
    with pytest.raises(ValueError):
        database.add(make_student())


def test_存在しないuuidは更新できない(tmp_path):
    database = DatabaseController(tmp_path / "students.msgpack")
    with pytest.raises(KeyError):
        database.update(make_student())


def test_保存後に一時ファイルが残らない(tmp_path):
    database = DatabaseController(tmp_path / "students.msgpack")
    database.add(make_student())
    assert [p.name for p in tmp_path.iterdir()] == ["students.msgpack"]


def test_実行済みの年度は再起動後も読み込める(tmp_path):
    filepath = tmp_path / "students.msgpack"
    DatabaseController(filepath).commit_year_update([], 2027)
    assert DatabaseController(filepath).completed_fiscal_years() == {2027}


def test_年度更新に存在しない学生が含まれていたらエラーで何も保存しない(tmp_path):
    filepath = tmp_path / "students.msgpack"
    database = DatabaseController(filepath)
    with pytest.raises(KeyError):
        database.commit_year_update([make_student("no-such-uuid")], 2027)
    assert database.completed_fiscal_years() == set()
