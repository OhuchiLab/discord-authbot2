"""
[API] controllers パッケージの公開 I/F のテスト

`build_controllers()` で組み立てたコントローラー一式を、本物の database (一時フォルダのファイル) と組み合わせて使います。
Discord とメール送信だけは偽物です。
"""

import pytest

from controllers import BotControllers, StudentRegistrationError, build_controllers
from database import DatabaseController
from several_types import AUTHORIZED_ROLE, Grade
from tests.fakes import FakeDiscordGateway, FakeMailSender

USER_ID = "111"


@pytest.fixture
def discord() -> FakeDiscordGateway:
    return FakeDiscordGateway()


@pytest.fixture
def mail() -> FakeMailSender:
    return FakeMailSender()


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "students.msgpack"


@pytest.fixture
def controllers(database_path, mail, discord) -> BotControllers:
    return build_controllers(DatabaseController(database_path), mail, discord, "shizuoka.ac.jp")


async def test_登録から認証完了まで_結果がファイルに保存される(controllers, database_path, mail, discord):
    controllers.student.register_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    discord.add_member(USER_ID)

    await controllers.onboarding.welcome_new_member(USER_ID, "yamada")
    for text in ["山田 太郎", "AB123456", "M1", "yamada@shizuoka.ac.jp"]:
        await controllers.onboarding.receive_direct_message(USER_ID, text)
    await controllers.onboarding.receive_direct_message(USER_ID, mail.last_code())

    assert AUTHORIZED_ROLE.name in discord.members[USER_ID].roles
    reloaded = DatabaseController(database_path)
    assert reloaded.find_by_discord_id(USER_ID).name == "山田 太郎"


def test_登録エラーは公開されている例外で受け取れる(controllers):
    controllers.student.register_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    with pytest.raises(StudentRegistrationError):
        controllers.student.register_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")


async def test_コントローラー同士は同じ学生情報を共有している(controllers):
    student = controllers.student.register_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    controllers.student.link_discord_id(student.uuid, USER_ID)
    # student で紐付けた結果が、auth_flow からも見えている
    reply = await controllers.auth_flow.handle_message(USER_ID, "こんにちは")
    assert reply.text == "すでに認証済みです。"
