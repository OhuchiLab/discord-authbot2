"""
[機能] F8 ロールの準備 (Bot の起動時)
"""

from several_types import ALL_ROLES


async def test_起動するとBotが使うロールがすべてサーバーに作られる(driver):
    await driver.bot_becomes_ready()
    assert {role.name for role in ALL_ROLES} <= driver.discord.guild_roles


async def test_ロールを作る権限が無くてもBotは止まらない(driver):
    driver.discord.can_manage_roles = False
    await driver.bot_becomes_ready()
    assert await driver.run_command("1", "health_check") == "I'm alive!"
