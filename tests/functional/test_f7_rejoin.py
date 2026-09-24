"""
[機能] F7 再参加時の自動復元
"""

from several_types import AUTHORIZED_ROLE, GRADE_ROLES, UNAUTHORIZED_ROLE, Grade

USER_ID = "111"


async def test_認証済みの人がBot再起動後に再参加すると_手続きなしでロールが戻る(driver):
    await driver.register_yamada()
    await driver.member_joins(USER_ID)
    await driver.answer_questions_as_yamada(USER_ID)

    # サーバーを抜け、Bot が再起動した後に、もう一度参加する
    del driver.discord.members[USER_ID]
    driver.restart_bot()
    await driver.member_joins(USER_ID)

    member = driver.discord.members[USER_ID]
    assert member.roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}
    assert UNAUTHORIZED_ROLE.name not in member.roles
    assert "おかえりなさい" in driver.discord.last_dm(USER_ID)


async def test_サーバー外で認証を終えた人は_参加時にロールが付く(driver):
    await driver.register_yamada()
    await driver.send_dm(USER_ID, "こんにちは")  # サーバーに参加する前に DM で手続きをする

    last_dm = await driver.answer_questions_as_yamada(USER_ID)
    assert "サーバーに参加すると自動で付与されます" in last_dm

    await driver.member_joins(USER_ID)
    assert AUTHORIZED_ROLE.name in driver.discord.members[USER_ID].roles
