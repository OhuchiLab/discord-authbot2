"""
[単体] tools.firebase_migration.firebase_source (Firestore / Firebase Auth からの読み込み) のテスト

firebase-admin の代わりに、同じ名前の偽物のモジュールを差し込んで確認します (Firebase には接続しない)。
"""

import sys
import types

import pytest

from tools.firebase_migration.converter import FirebaseMember
from tools.firebase_migration.firebase_source import load_from_firebase


class FakeDocument:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class FakeUser:
    def __init__(self, email, email_verified):
        self.email = email
        self.email_verified = email_verified


@pytest.fixture
def fake_firebase_admin(monkeypatch):
    """firebase_admin とその下のモジュールの偽物を sys.modules に差し込む"""
    state = {"collection": None, "deleted": False}
    documents = [
        FakeDocument("doc-1", {"name": "山田 太郎", "student_number": "AB123456", "grade": "M1", "mail": "a@x", "discordId": "101"}),
        FakeDocument("doc-2", {"name": "鈴木 花子"}),
    ]
    users = [FakeUser("Yamada@Shizuoka.ac.jp", True), FakeUser("suzuki@shizuoka.ac.jp", False), FakeUser(None, True)]

    firebase_admin = types.ModuleType("firebase_admin")
    firebase_admin.initialize_app = lambda credential, name: "app"
    firebase_admin.delete_app = lambda app: state.update(deleted=True)

    credentials = types.ModuleType("firebase_admin.credentials")
    credentials.Certificate = lambda path: ("certificate", path)

    firestore = types.ModuleType("firebase_admin.firestore")

    class Client:
        def collection(self, name):
            state["collection"] = name
            return types.SimpleNamespace(stream=lambda: iter(documents))

    firestore.client = lambda app: Client()

    auth = types.ModuleType("firebase_admin.auth")
    auth.list_users = lambda app: types.SimpleNamespace(iterate_all=lambda: iter(users))

    firebase_admin.credentials, firebase_admin.firestore, firebase_admin.auth = credentials, firestore, auth
    for name, module in {
        "firebase_admin": firebase_admin,
        "firebase_admin.credentials": credentials,
        "firebase_admin.firestore": firestore,
        "firebase_admin.auth": auth,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    return state


def test_membersコレクションとメール認証済みのアドレスを読み込む(fake_firebase_admin, tmp_path):
    key = tmp_path / "key.json"
    key.write_text("{}")

    members, verified_emails = load_from_firebase(str(key))

    assert fake_firebase_admin["collection"] == "members"
    assert members == [
        FirebaseMember("doc-1", "山田 太郎", "AB123456", "M1", "a@x", "101"),
        FirebaseMember("doc-2", "鈴木 花子", None, None, None, None),
    ]
    assert verified_emails == {"yamada@shizuoka.ac.jp"}  # 小文字にそろえ、未認証とメールなしは含めない
    assert fake_firebase_admin["deleted"]  # 接続を後片付けする


def test_鍵のファイルが無ければ理由を示して終了する(fake_firebase_admin, tmp_path):
    with pytest.raises(SystemExit, match="サービスアカウントの鍵が見つかりません"):
        load_from_firebase(str(tmp_path / "no-such-key.json"))
