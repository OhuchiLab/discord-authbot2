"""
[単体] controllers.StudentDeleteController (学生情報の削除) のテスト

データベースと Discord は偽物に置き換えています。
StudentController と RoleController は、副作用の無い業務ルールなので本物を使います。
"""

import pytest

from controllers import RoleController, StudentController, StudentDeleteController, StudentDeleteError
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
def controller(students, discord) -> StudentDeleteController:
    return StudentDeleteController(students, RoleController(discord))


@pytest.fixture
def linked(students, discord) -> StudentInfo:
    """認証済みでサーバーにいる学生"""
    student = students.register_student("山田 太郎", "AB123456", Grade.B4, "yamada@shizuoka.ac.jp")
    discord.add_member(USER_ID, roles=(AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.B4].name))
    return students.link_discord_id(student.uuid, USER_ID)


def test_学籍番号でもDiscordIDでも対象を指定できる(controller, linked):
    assert controller.prepare(student_number="AB123456") == linked
    assert controller.prepare(discord_id=USER_ID) == linked


def test_対象の指定が正しくなければ削除用のエラーになる(controller, linked):
    with pytest.raises(StudentDeleteError, match="どちらか一方を指定してください"):
        controller.prepare()
    with pytest.raises(StudentDeleteError, match="見つかりません"):
        controller.prepare(student_number="ZZ999999")


async def test_認証済みの学生を削除すると未認証の状態に戻す(controller, linked, discord, students):
    result = await controller.commit(linked)

    assert students.find_by_uuid(linked.uuid) is None
    assert result.discord_synced
    assert discord.members[USER_ID].roles == {UNAUTHORIZED_ROLE.name}


async def test_未認証の学生の削除ではDiscordを操作しない(controller, students):
    student = students.register_student("鈴木 花子", "CD123456", Grade.M1, "suzuki@shizuoka.ac.jp")

    result = await controller.commit(student)

    assert students.find_by_uuid(student.uuid) is None
    assert not result.discord_synced
    assert not result.not_in_server


async def test_サーバーにいない学生も削除する(controller, linked, discord, students):
    del discord.members[USER_ID]
    result = await controller.commit(linked)
    assert students.find_by_uuid(linked.uuid) is None
    assert result.not_in_server


async def test_ロールを外せなくても削除する(controller, linked, discord, students):
    discord.can_manage_roles = False
    result = await controller.commit(linked)
    assert students.find_by_uuid(linked.uuid) is None
    assert result.problems
