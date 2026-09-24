"""
[単体] controllers.OnboardingController のテスト

Discord・メール送信・データベースは偽物に置き換えています。
組み合わせる他のコントローラーは、副作用の無い業務ルールなので本物を使います。
"""

import pytest

from controllers import AuthFlowController, OnboardingController, RoleController, StudentController
from several_types import AUTHORIZED_ROLE, GRADE_ROLES, UNAUTHORIZED_ROLE, Grade
from tests.fakes import FakeDiscordGateway, FakeMailSender, InMemoryDatabase

USER_ID = "111"
CODE = "123456"


@pytest.fixture
def discord() -> FakeDiscordGateway:
    return FakeDiscordGateway()


@pytest.fixture
def students() -> StudentController:
    controller = StudentController(InMemoryDatabase(), "shizuoka.ac.jp")
    controller.register_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    return controller


@pytest.fixture
def onboarding(students, discord) -> OnboardingController:
    auth_flow = AuthFlowController(students, FakeMailSender(), "shizuoka.ac.jp", code_generator=lambda: CODE)
    return OnboardingController(students, auth_flow, RoleController(discord), discord)


def link_yamada(students: StudentController) -> None:
    student = students.find_matching_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    students.link_discord_id(student.uuid, USER_ID)


async def answer_all(onboarding: OnboardingController) -> None:
    for text in ["山田 太郎", "AB123456", "M1", "yamada@shizuoka.ac.jp", CODE]:
        await onboarding.receive_direct_message(USER_ID, text)


async def test_初めてのメンバーには未認証ロールを付けて質問を始める(onboarding, discord):
    member = discord.add_member(USER_ID)
    await onboarding.welcome_new_member(USER_ID, "yamada")
    assert member.roles == {UNAUTHORIZED_ROLE.name}
    assert "ようこそ yamada さん" in discord.last_dm(USER_ID)
    assert "名前 (フルネーム)" in discord.last_dm(USER_ID)


async def test_認証済みのメンバーが再参加したらロールを付け直す(onboarding, discord, students):
    link_yamada(students)
    member = discord.add_member(USER_ID)
    await onboarding.welcome_new_member(USER_ID, "yamada")
    assert AUTHORIZED_ROLE.name in member.roles
    assert "おかえりなさい" in discord.last_dm(USER_ID)


async def test_DMで答えていくと認証が完了してロールが付く(onboarding, discord):
    member = discord.add_member(USER_ID, roles=(UNAUTHORIZED_ROLE.name,))
    assert "DM を送信しました" in await onboarding.request_auth(USER_ID)

    await answer_all(onboarding)

    assert member.roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}
    assert "認証が完了しました" in discord.last_dm(USER_ID)


async def test_サーバーにいない人が認証を終えたら参加を案内する(onboarding, discord):
    await onboarding.receive_direct_message(USER_ID, "こんにちは")  # 手続き中でなければ手続きが始まる
    await answer_all(onboarding)
    assert "サーバーに参加すると自動で付与されます" in discord.last_dm(USER_ID)


async def test_authでDMを送れなければ設定変更を案内する(onboarding, discord):
    discord.add_member(USER_ID, accepts_dm=False)
    assert "DM を送信できませんでした" in await onboarding.request_auth(USER_ID)


async def test_認証済みの人がauthを実行したらロールを付け直す(onboarding, discord, students):
    link_yamada(students)
    member = discord.add_member(USER_ID)
    assert "すでに認証済みです" in await onboarding.request_auth(USER_ID)
    assert AUTHORIZED_ROLE.name in member.roles


async def test_DMを拒否している新メンバーでもエラーにしない(onboarding, discord):
    member = discord.add_member(USER_ID, accepts_dm=False)
    await onboarding.welcome_new_member(USER_ID, "yamada")
    assert member.roles == {UNAUTHORIZED_ROLE.name}
