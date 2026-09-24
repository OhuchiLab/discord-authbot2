"""
[単体] database.DatabaseBackup と、DatabaseController のバックアップ連携のテスト (一時フォルダの実ファイルを使用)
"""

from datetime import datetime, timedelta

import pytest

from database import DatabaseBackup, DatabaseController, open_database
from several_types import Grade, StudentInfo


def make_student(uuid: str) -> StudentInfo:
    return StudentInfo(uuid, "山田 太郎", f"{uuid:0>8}", f"{uuid}@shizuoka.ac.jp", Grade.M1)


class StepClock:
    """呼ばれるたびに 1 秒進む時計"""

    def __init__(self):
        self.current = datetime(2027, 3, 1, 9, 0, 0)

    def __call__(self) -> datetime:
        self.current += timedelta(seconds=1)
        return self.current


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "students.msgpack"
    path.write_bytes(b"original")
    return path


def test_日時付きの名前でコピーを作る(tmp_path, source):
    backup = DatabaseBackup(tmp_path / "backups", keep=5, now=lambda: datetime(2027, 3, 1, 9, 30, 15, 123456))

    created = backup.create(source)

    assert created == tmp_path / "backups" / "students-20270301-093015-123456.msgpack"
    assert created.read_bytes() == b"original"


def test_決められた数を超えたら古いものから消す(tmp_path, source):
    backup = DatabaseBackup(tmp_path / "backups", keep=2, now=StepClock())

    created = [backup.create(source) for _ in range(4)]

    assert sorted((tmp_path / "backups").iterdir()) == created[-2:]


def test_他の名前のファイルは消さない(tmp_path, source):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "memo.txt").write_text("keep me")
    backup = DatabaseBackup(backup_dir, keep=1, now=StepClock())

    backup.create(source)
    backup.create(source)

    assert (backup_dir / "memo.txt").exists()


def test_残す数は1以上(tmp_path):
    with pytest.raises(ValueError):
        DatabaseBackup(tmp_path, keep=0)


# ----------------------------------------------------------------------
# DatabaseController との連携
# ----------------------------------------------------------------------


def test_保存するたびにバックアップを取る(tmp_path):
    database = open_database(tmp_path / "students.msgpack", tmp_path / "backups", 10)

    database.add(make_student("1"))
    database.add(make_student("2"))

    files = sorted((tmp_path / "backups").iterdir())
    assert len(files) == 2
    assert files[-1].read_bytes() == (tmp_path / "students.msgpack").read_bytes()


def test_起動時にファイルがあればバックアップを取る(tmp_path):
    DatabaseController(tmp_path / "students.msgpack").add(make_student("1"))

    open_database(tmp_path / "students.msgpack", tmp_path / "backups", 10)

    assert len(list((tmp_path / "backups").iterdir())) == 1


def test_起動時にファイルが無ければバックアップを取らない(tmp_path):
    open_database(tmp_path / "students.msgpack", tmp_path / "backups", 10)
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize(("backup_dir_name", "keep"), [(None, 10), ("backups", 0)])
def test_保存先が無いか残す数が0ならバックアップを取らない(tmp_path, backup_dir_name, keep):
    backup_dir = tmp_path / backup_dir_name if backup_dir_name else None
    database = open_database(tmp_path / "students.msgpack", backup_dir, keep)

    database.add(make_student("1"))

    assert not (tmp_path / "backups").exists()


def test_dumpはファイルと同じ内容のバイト列を返す(tmp_path):
    database = DatabaseController(tmp_path / "students.msgpack")
    database.add(make_student("1"))
    assert database.dump() == (tmp_path / "students.msgpack").read_bytes()
