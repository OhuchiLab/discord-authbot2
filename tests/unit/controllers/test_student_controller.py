"""
[単体] controllers.StudentController のテスト

データベースは偽物 (InMemoryDatabase) に置き換えています。
"""

import pytest

from controllers import StudentController, StudentLinkError, StudentRegistrationError
from several_types import Grade
from tests.fakes import InMemoryDatabase


@pytest.fixture
def database() -> InMemoryDatabase:
    return InMemoryDatabase()


@pytest.fixture
def controller(database) -> StudentController:
    return StudentController(database, "shizuoka.ac.jp")


def register_yamada(controller: StudentController):
    return controller.register_student("山田 太郎", "ab123456", Grade.M1, "Yamada.Taro.21@shizuoka.ac.jp")


def test_登録時に学籍番号は大文字_メールは小文字にそろえて保存する(controller, database):
    student = register_yamada(controller)
    assert database.get_all() == [student]
    assert student.student_number == "AB123456"
    assert student.email == "yamada.taro.21@shizuoka.ac.jp"
    assert student.discord_id is None


@pytest.mark.parametrize(
    ("student_number", "email"),
    [
        ("1234567", "a@shizuoka.ac.jp"),  # 学籍番号が 7 文字
        ("12345678", "a@gmail.com"),  # 大学以外のドメイン
        ("12345678", "a@evil.shizuoka.ac.jp"),  # サブドメイン
        ("12345678", "shizuoka.ac.jp"),  # @ が無い
    ],
)
def test_形式が不正な値は登録できない(controller, student_number, email):
    with pytest.raises(StudentRegistrationError):
        controller.register_student("山田 太郎", student_number, Grade.M1, email)


def test_学籍番号とメールアドレスの重複は登録できない(controller):
    register_yamada(controller)
    with pytest.raises(StudentRegistrationError, match="学籍番号"):
        controller.register_student("別人", "AB123456", Grade.M1, "other@shizuoka.ac.jp")
    with pytest.raises(StudentRegistrationError, match="メールアドレス"):
        controller.register_student("別人", "CD123456", Grade.M1, "yamada.taro.21@shizuoka.ac.jp")


def test_照合では空白_全角_大文字小文字の違いを無視する(controller):
    registered = register_yamada(controller)
    found = controller.find_matching_student("山田　太郎", "ａｂ１２３４５６", Grade.M1, "YAMADA.TARO.21@shizuoka.ac.jp")
    assert found == registered


def test_学年が違えば照合に失敗する(controller):
    register_yamada(controller)
    assert controller.find_matching_student("山田 太郎", "AB123456", Grade.M2, "yamada.taro.21@shizuoka.ac.jp") is None


def test_DiscordIDを紐付けて保存できる(controller, database):
    student = register_yamada(controller)
    linked = controller.link_discord_id(student.uuid, "111")
    assert linked.discord_id == "111"
    assert database.find_by_discord_id("111") == linked


def test_別のアカウントに紐付け済みの学生情報には紐付けられない(controller):
    student = register_yamada(controller)
    controller.link_discord_id(student.uuid, "111")
    with pytest.raises(StudentLinkError):
        controller.link_discord_id(student.uuid, "222")


def test_1つのアカウントを2人の学生情報に紐付けることはできない(controller):
    yamada = register_yamada(controller)
    suzuki = controller.register_student("鈴木 花子", "CD123456", Grade.B4, "suzuki@shizuoka.ac.jp")
    controller.link_discord_id(yamada.uuid, "111")
    with pytest.raises(StudentLinkError):
        controller.link_discord_id(suzuki.uuid, "111")


def test_存在しない学生情報には紐付けられない(controller):
    with pytest.raises(StudentLinkError):
        controller.link_discord_id("no-such-uuid", "111")
