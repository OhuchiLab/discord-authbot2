"""
[機能] 移行ツール (tools/firebase_migration): 旧 Bot の Firestore のデータを新 Bot の学生情報ファイルに移す

Firebase には接続せず、Firestore から読み込む部分だけを偽物に置き換えて、ツールを最初から最後まで動かします。
"""

import pytest

from database import DatabaseController
from several_types import Grade
from tools.firebase_migration import migrate
from tools.firebase_migration.converter import FirebaseMember

MEMBERS = [
    FirebaseMember("doc-1", "山田 太郎", "AB123456", "M1", "yamada@shizuoka.ac.jp", "101"),
    FirebaseMember("doc-2", "鈴木 花子", "CD123456", "B4", "suzuki@shizuoka.ac.jp", "102"),  # メール未認証
    FirebaseMember("doc-3", "佐藤 次郎", "1234", "B4", "sato@shizuoka.ac.jp", None),  # 学籍番号が不正
]
VERIFIED_EMAILS = {"yamada@shizuoka.ac.jp"}


@pytest.fixture(autouse=True)
def fake_firebase(monkeypatch):
    """Firestore / Firebase Auth から読み込む代わりに、決まったデータを返す"""
    calls = []

    def load(credentials_path):
        calls.append(credentials_path)
        return MEMBERS, VERIFIED_EMAILS

    monkeypatch.setattr(migrate, "load_from_firebase", load)
    return calls


def run(tmp_path, *extra_args) -> tuple[int, object]:
    database_path = tmp_path / "students.msgpack"
    args = ["--credentials", str(tmp_path / "key.json"), "--database", str(database_path), *extra_args]
    return migrate.main(args), database_path


def test_既定では確認だけして何も書き込まない(tmp_path, capsys, fake_firebase):
    exit_code, database_path = run(tmp_path)

    assert exit_code == 0
    assert fake_firebase == [str(tmp_path / "key.json")]
    assert not database_path.exists()
    out = capsys.readouterr().out
    assert "移す人: 2 人 (認証済み 1 人 / 未認証 1 人)" in out
    assert "飛ばす人: 1 人" in out
    assert "doc-3 佐藤 次郎: 学籍番号は英数字 8 文字" in out
    assert "doc-2 鈴木 花子: メール認証が済んでいないため" in out
    assert "--apply" in out


def test_applyを付けると学生情報ファイルに書き込む(tmp_path, capsys):
    exit_code, database_path = run(tmp_path, "--apply", "--backup-dir", str(tmp_path / "backups"))

    assert exit_code == 0
    students = {s.uuid: s for s in DatabaseController(database_path).get_all()}
    assert set(students) == {"doc-1", "doc-2"}
    assert (students["doc-1"].grade, students["doc-1"].discord_id) == (Grade.M1, "101")
    assert students["doc-2"].discord_id is None
    assert "2 人を移しました" in capsys.readouterr().out
    assert len(list((tmp_path / "backups").iterdir())) == 1  # 書き込んだ直後のバックアップ


def test_移行先にすでに学生情報があれば書き込まない(tmp_path, capsys):
    database_path = tmp_path / "students.msgpack"
    _, _ = run(tmp_path, "--apply", "--backup-dir", str(tmp_path / "backups"))
    before = database_path.read_bytes()

    exit_code, _ = run(tmp_path, "--apply", "--backup-dir", str(tmp_path / "backups"))

    assert exit_code == 1
    assert database_path.read_bytes() == before
    assert "移行先にすでに学生情報があります" in capsys.readouterr().out
