"""
[単体] controllers.StudentController のテスト

データベースは偽物 (InMemoryDatabase) に置き換えています。
"""

import pytest

from controllers import StudentController, StudentEditError, StudentLinkError, StudentRegistrationError
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


# ----------------------------------------------------------------------
# 学生情報の変更 (prepare_edit / apply_edit)
# ----------------------------------------------------------------------


def test_学籍番号で学生情報を探せる(controller):
    student = register_yamada(controller)
    assert controller.find_by_student_number(" ab123456 ") == student
    assert controller.find_by_student_number("ZZ999999") is None


def test_変更内容を作っただけでは保存しない(controller, database):
    student = register_yamada(controller)
    save_count = database.save_count

    edit = controller.prepare_edit(student, new_name="山田 次郎", new_grade=Grade.M2)

    assert (edit.before, edit.after.name, edit.after.grade) == (student, "山田 次郎", Grade.M2)
    assert edit.changed_fields() == ["氏名", "学年"]
    assert database.save_count == save_count


def test_変更後の学籍番号とメールアドレスは正規化する(controller):
    student = register_yamada(controller)
    edit = controller.prepare_edit(student, new_student_number="cd654321", new_email="New@Shizuoka.ac.jp")
    assert (edit.after.student_number, edit.after.email) == ("CD654321", "new@shizuoka.ac.jp")


def test_紐付けを解除する変更を作れる(controller):
    linked = controller.link_discord_id(register_yamada(controller).uuid, "111")
    edit = controller.prepare_edit(linked, unlink_discord=True)
    assert edit.after.discord_id is None
    assert edit.unlinks_discord


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({}, "変更する項目を指定してください。"),
        ({"new_grade": Grade.M1}, "変更する項目を指定してください。"),  # 今と同じ値
        ({"new_name": "　"}, "氏名が空です。"),
        ({"new_student_number": "1234"}, "学籍番号は英数字 8 文字"),
        ({"new_email": "a@gmail.com"}, "@shizuoka.ac.jp"),
        ({"unlink_discord": True}, "紐付いていません"),
    ],
)
def test_不正な変更はエラー(controller, changes, message):
    student = register_yamada(controller)
    with pytest.raises(StudentEditError, match=message):
        controller.prepare_edit(student, **changes)


def test_他の学生と重複する学籍番号_メールアドレスには変更できない(controller):
    yamada = register_yamada(controller)
    controller.register_student("鈴木 花子", "CD123456", Grade.B4, "suzuki@shizuoka.ac.jp")
    with pytest.raises(StudentEditError, match="学籍番号 CD123456 はすでに登録されています"):
        controller.prepare_edit(yamada, new_student_number="cd123456")
    with pytest.raises(StudentEditError, match="メールアドレス suzuki@shizuoka.ac.jp はすでに登録されています"):
        controller.prepare_edit(yamada, new_email="suzuki@shizuoka.ac.jp")


def test_自分自身の値とは重複扱いしない(controller):
    yamada = register_yamada(controller)
    edit = controller.prepare_edit(yamada, new_student_number="ab123456", new_name="山田 次郎")
    assert edit.changed_fields() == ["氏名"]


def test_変更を保存できる(controller, database):
    student = register_yamada(controller)
    edit = controller.prepare_edit(student, new_grade=Grade.M2)

    saved = controller.apply_edit(edit)

    assert saved.grade == Grade.M2
    assert database.find_by_uuid(student.uuid) == saved


def test_変更内容を作った後に学生情報が変わっていたら保存しない(controller, database):
    student = register_yamada(controller)
    edit = controller.prepare_edit(student, new_grade=Grade.M2)
    controller.apply_edit(controller.prepare_edit(student, new_name="山田 次郎"))

    with pytest.raises(StudentEditError, match="やり直してください"):
        controller.apply_edit(edit)
    assert database.find_by_uuid(student.uuid).grade == Grade.M1


def test_変更内容を作った後に重複が生じていたら保存しない(controller):
    student = register_yamada(controller)
    edit = controller.prepare_edit(student, new_student_number="CD123456")
    controller.register_student("鈴木 花子", "CD123456", Grade.B4, "suzuki@shizuoka.ac.jp")

    with pytest.raises(StudentEditError, match="すでに登録されています"):
        controller.apply_edit(edit)
