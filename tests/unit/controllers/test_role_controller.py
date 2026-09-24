"""
[単体] controllers.RoleController のテスト

Discord の操作は偽物 (FakeDiscordGateway) に置き換えています。
"""

import pytest

from controllers import RoleController
from external import MemberNotFoundError
from several_types import (
    ADMINISTRATOR_ROLE,
    ALL_ROLES,
    AUTHORIZED_ROLE,
    GRADE_ROLES,
    UNAUTHORIZED_ROLE,
    Grade,
    StudentInfo,
)
from tests.fakes import FakeDiscordGateway

USER_ID = "111"
STUDENT = StudentInfo("uuid-1", "山田 太郎", "AB123456", "yamada@shizuoka.ac.jp", Grade.M1, USER_ID)


@pytest.fixture
def discord() -> FakeDiscordGateway:
    return FakeDiscordGateway()


@pytest.fixture
def controller(discord) -> RoleController:
    return RoleController(discord)


async def test_すべてのロールをサーバーに作成する(controller, discord):
    await controller.setup_roles()
    assert discord.guild_roles == {role.name for role in ALL_ROLES}


async def test_ロール作成に失敗してもエラーにしない(controller, discord):
    discord.can_manage_roles = False
    await controller.setup_roles()
    discord.bot_in_guild = False
    await controller.setup_roles()


async def test_未認証ロールを付与する(controller, discord):
    member = discord.add_member(USER_ID)
    await controller.mark_as_unauthorized(USER_ID)
    assert member.roles == {UNAUTHORIZED_ROLE.name}


async def test_認証済みにするとニックネームとロールが設定される(controller, discord):
    member = discord.add_member(USER_ID, roles=(UNAUTHORIZED_ROLE.name,))

    problems = await controller.mark_as_authorized(USER_ID, STUDENT)

    assert problems == []
    assert member.nickname == "山田 太郎"
    assert member.roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}


async def test_学年が変わっていれば古い学年ロールを外す(controller, discord):
    member = discord.add_member(USER_ID, roles=(GRADE_ROLES[Grade.B4].name,))
    await controller.mark_as_authorized(USER_ID, STUDENT)
    assert member.roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}


async def test_ニックネームを変更できなくてもロールは付与する(controller, discord):
    member = discord.add_member(USER_ID, nickname_editable=False)

    problems = await controller.mark_as_authorized(USER_ID, STUDENT)

    assert len(problems) == 1 and "ニックネーム" in problems[0]
    assert AUTHORIZED_ROLE.name in member.roles


async def test_ロールを付与できなければ説明を返す(controller, discord):
    discord.add_member(USER_ID)
    discord.can_manage_roles = False

    problems = await controller.mark_as_authorized(USER_ID, STUDENT)

    assert len(problems) == 1 and "ロール" in problems[0]


async def test_サーバーにいないメンバーは認証済みにできない(controller):
    with pytest.raises(MemberNotFoundError):
        await controller.mark_as_authorized(USER_ID, STUDENT)


async def test_Administratorロールを持つメンバーだけが管理者(controller, discord):
    discord.add_member("1", roles=(ADMINISTRATOR_ROLE.name,))
    discord.add_member("2", roles=(AUTHORIZED_ROLE.name,))
    assert await controller.is_admin("1")
    assert not await controller.is_admin("2")
    assert not await controller.is_admin("not-a-member")


async def test_学年ロールの同期ではニックネームを変えずに学年ロールだけ付け替える(controller, discord):
    member = discord.add_member(USER_ID, roles=(AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.B4].name))
    graduated = StudentInfo("uuid-1", "山田 太郎", "AB123456", "yamada@shizuoka.ac.jp", Grade.OBOG, USER_ID)

    problems = await controller.sync_grade_role(USER_ID, graduated)

    assert problems == []
    assert member.nickname is None
    assert member.roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.OBOG].name}


async def test_学年ロールを付け替えられなければ説明を返す(controller, discord):
    discord.add_member(USER_ID, roles=(GRADE_ROLES[Grade.B4].name,))
    discord.can_manage_roles = False
    assert len(await controller.sync_grade_role(USER_ID, STUDENT)) == 1
