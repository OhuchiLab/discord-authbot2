"""
[機能] F6 認証の再開 (/auth)
"""

from several_types import AUTHORIZED_ROLE

USER_ID = "111"


async def test_未認証の人が実行するとDMで手続きが始まる(driver):
    driver.discord.add_member(USER_ID)

    reply = await driver.run_command(USER_ID, "auth")

    assert reply == "DM を送信しました。DM で質問に答えてください。"
    assert "名前 (フルネーム) を教えてください。" in driver.discord.last_dm(USER_ID)


async def test_DMを受け取らない設定の人には設定変更を案内する(driver):
    driver.discord.add_member(USER_ID, accepts_dm=False)
    assert "DM を送信できませんでした" in await driver.run_command(USER_ID, "auth")


async def test_認証済みの人が実行するとロールを付け直す(driver):
    await driver.register_yamada()
    await driver.member_joins(USER_ID)
    await driver.answer_questions_as_yamada(USER_ID)
    driver.discord.members[USER_ID].roles.clear()  # 誰かが誤ってロールを外した

    reply = await driver.run_command(USER_ID, "auth")

    assert "すでに認証済みです" in reply
    assert AUTHORIZED_ROLE.name in driver.discord.members[USER_ID].roles
