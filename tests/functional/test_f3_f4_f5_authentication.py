"""
[機能] F3 参加時の案内 / F4 DM での認証手続き / F5 認証完了の処理

新メンバーがサーバーに参加してから、認証が完了するまでの一連の流れを確認します。
"""

from database import DatabaseController
from several_types import AUTHORIZED_ROLE, GRADE_ROLES, UNAUTHORIZED_ROLE, Grade

USER_ID = "111"


async def test_F3_参加すると未認証ロールが付き_DMで質問が届く(driver):
    await driver.member_joins(USER_ID, display_name="yamada")

    assert driver.discord.members[USER_ID].roles == {UNAUTHORIZED_ROLE.name}
    assert "ようこそ yamada さん" in driver.discord.last_dm(USER_ID)
    assert "名前 (フルネーム) を教えてください。" in driver.discord.last_dm(USER_ID)


async def test_F4_F5_質問に答えて認証コードを送ると認証が完了する(driver):
    await driver.register_yamada()
    await driver.member_joins(USER_ID)

    assert await driver.send_dm(USER_ID, "山田 太郎") == "学籍番号を教えてください。"
    assert "学年を以下から" in await driver.send_dm(USER_ID, "AB123456")
    assert "メールアドレス" in await driver.send_dm(USER_ID, "M1")
    assert "認証コードを送信しました" in await driver.send_dm(USER_ID, "yamada@shizuoka.ac.jp")
    assert driver.mail.sent[-1].to_address == "yamada@shizuoka.ac.jp"

    last_dm = await driver.send_dm(USER_ID, driver.mail.last_code())

    # F5: ニックネーム・ロールが設定され、完了が DM で知らされる
    member = driver.discord.members[USER_ID]
    assert member.nickname == "山田 太郎"
    assert member.roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}
    assert "認証が完了しました" in last_dm
    # 認証結果はファイルに保存されている
    assert DatabaseController(driver.database_path).find_by_discord_id(USER_ID).name == "山田 太郎"


async def test_F4_登録内容と違えば認証できない(driver):
    await driver.register_yamada()
    await driver.member_joins(USER_ID)

    for text in ["山田 次郎", "AB123456", "M1"]:
        await driver.send_dm(USER_ID, text)
    reply = await driver.send_dm(USER_ID, "yamada@shizuoka.ac.jp")

    assert "一致しませんでした" in reply
    assert driver.mail.sent == []
    assert driver.discord.members[USER_ID].roles == {UNAUTHORIZED_ROLE.name}


async def test_F4_Botを再起動すると手続きは最初からになる(driver):
    await driver.register_yamada()
    await driver.member_joins(USER_ID)
    await driver.send_dm(USER_ID, "山田 太郎")

    driver.restart_bot()

    assert "名前 (フルネーム) を教えてください。" in await driver.send_dm(USER_ID, "AB123456")


async def test_F4_サーバー内の投稿には反応しない(driver):
    await driver.member_joins(USER_ID)
    dm_count = len(driver.discord.dms[USER_ID])

    await driver.post_in_server(USER_ID, "山田 太郎")

    assert len(driver.discord.dms[USER_ID]) == dm_count


async def test_F5_ニックネームを変更できないメンバーには理由を伝える(driver):
    await driver.register_yamada()
    await driver.member_joins(USER_ID, nickname_editable=False)

    last_dm = await driver.answer_questions_as_yamada(USER_ID)

    assert "ニックネームを変更できませんでした" in last_dm
    assert AUTHORIZED_ROLE.name in driver.discord.members[USER_ID].roles
