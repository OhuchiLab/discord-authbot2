"""
[単体] controllers.StudentEditController (学生情報の手動変更) のテスト

データベースと Discord は偽物に置き換えています。
StudentController と RoleController は、副作用の無い業務ルールなので本物を使います。
"""

import pytest

from controllers import RoleController, StudentController, StudentEditController, StudentEditError
from several_types import AUTHORIZED_ROLE, GRADE_ROLES, UNAUTHORIZED_ROLE, Grade, StudentInfo
from tests.fakes import FakeDiscordGateway, InMemoryDatabase

USER_ID = "101"


@pytest.fixture
def discord() -> FakeDiscordGateway:
    return FakeDiscordGateway()


@pytest.fixture
def students() -> StudentController:
    return StudentController(InMemoryDatabase(), "shizuoka.ac.jp")


@pytest.fixture
def controller(students, discord) -> StudentEditController:
    return StudentEditController(students, RoleController(discord))


@pytest.fixture
def linked(students, discord) -> StudentInfo:
    """認証済みでサーバーにいる学生"""
    student = students.register_student("山田 太郎", "AB123456", Grade.B4, "yamada@shizuoka.ac.jp")
    discord.add_member(USER_ID, roles=(AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.B4].name))
    return students.link_discord_id(student.uuid, USER_ID)


# ----------------------------------------------------------------------
# 対象の指定
# ----------------------------------------------------------------------


def test_学籍番号でもDiscordIDでも対象を指定できる(controller, linked):
    assert controller.prepare(student_number="AB123456", new_grade=Grade.M1).before == linked
    assert controller.prepare(discord_id=USER_ID, new_grade=Grade.M1).before == linked


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ({}, "どちらか一方を指定してください"),
        ({"student_number": "AB123456", "discord_id": USER_ID}, "どちらか一方を指定してください"),
        ({"student_number": "ZZ999999"}, "学籍番号 ZZ999999 の学生情報が見つかりません。"),
        ({"discord_id": "999"}, "このメンバーに紐付いた学生情報が見つかりません。"),
    ],
)
def test_対象を正しく指定しないとエラー(controller, linked, target, message):
    with pytest.raises(StudentEditError, match=message):
        controller.prepare(**target, new_grade=Grade.M1)


# ----------------------------------------------------------------------
# 確定と Discord への反映
# ----------------------------------------------------------------------


async def test_学年を変えると学年ロールを付け替える(controller, linked, discord):
    result = await controller.commit(controller.prepare(student_number="AB123456", new_grade=Grade.M1))

    assert result.student.grade == Grade.M1
    assert result.discord_synced
    assert discord.members[USER_ID].roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}


async def test_氏名を変えるとニックネームを変える(controller, linked, discord):
    await controller.commit(controller.prepare(student_number="AB123456", new_name="山田 次郎"))
    assert discord.members[USER_ID].nickname == "山田 次郎"


async def test_メールアドレスだけの変更ではDiscordを操作しない(controller, linked, discord):
    result = await controller.commit(controller.prepare(student_number="AB123456", new_email="new@shizuoka.ac.jp"))
    assert not result.discord_synced
    assert discord.members[USER_ID].nickname is None


async def test_紐付けを解除すると未認証の状態に戻す(controller, linked, discord, students):
    result = await controller.commit(controller.prepare(student_number="AB123456", unlink_discord=True))

    assert result.discord_synced
    assert students.find_by_discord_id(USER_ID) is None
    assert discord.members[USER_ID].roles == {UNAUTHORIZED_ROLE.name}


async def test_サーバーにいない学生は学生情報だけ変える(controller, linked, discord):
    del discord.members[USER_ID]
    result = await controller.commit(controller.prepare(student_number="AB123456", new_grade=Grade.M1))
    assert result.student.grade == Grade.M1
    assert result.not_in_server


async def test_ロールを付け替えられなくても学生情報は変える(controller, linked, discord):
    discord.can_manage_roles = False
    result = await controller.commit(controller.prepare(student_number="AB123456", new_grade=Grade.M1))
    assert result.student.grade == Grade.M1
    assert result.problems
