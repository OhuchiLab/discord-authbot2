"""
[システム] 本物の Discord・SMTP につないで、Bot が動く状態であることを確認する (自動で確認できる部分)

メンバーの参加や DM の送信など、人が操作する部分は docs/test_design.md の手順書で確認します。
"""

import os

import pytest

from external import DiscordGateway
from several_types import ALL_ROLES


async def test_ST_A01_Botが対象のサーバーに参加している(running_bot):
    assert running_bot.get_guild(running_bot.config.guild_id) is not None


async def test_ST_A02_Botが使うロールがすべてサーバーにある(running_bot):
    await running_bot.controllers.role.setup_roles()
    guild = running_bot.get_guild(running_bot.config.guild_id)
    assert {role.name for role in ALL_ROLES} <= {role.name for role in guild.roles}


async def test_ST_A03_スラッシュコマンドがサーバーに登録されている(running_bot):
    commands = await running_bot.tree.fetch_commands(guild=running_bot.guild_object)
    assert {"health_check", "register", "auth"} <= {command.name for command in commands}


async def test_ST_A04_テスト担当者にDMを送れる(running_bot):
    user_id = os.getenv("SYSTEM_TEST_DISCORD_USER_ID")
    if not user_id:
        pytest.skip("SYSTEM_TEST_DISCORD_USER_ID (DM を受け取るテスト担当者の Discord ID) が未設定です")
    discord_gateway = DiscordGateway(running_bot, running_bot.config.guild_id)
    await discord_gateway.send_dm(user_id, "[システムテスト ST-A04] この DM が届いていれば成功です。")


async def test_ST_A05_認証メールを送れる(mail_sender):
    to_address = os.getenv("SYSTEM_TEST_MAIL_TO")
    if not to_address:
        pytest.skip("SYSTEM_TEST_MAIL_TO (テストメールの宛先) が未設定です")
    await mail_sender.send_verification_code(to_address, "000000", 10)
