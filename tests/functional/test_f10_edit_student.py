"""
[機能] F10 学生情報の手動変更 (/edit_student)

管理者が /edit_student で変更内容を指定 → 変更前後を確認 → 確定 すると、
学生情報 (ファイル) が変更され、認証済みの学生なら Discord のニックネーム・ロールにも反映されることを確認します。
"""

from database import DatabaseController
from several_types import AUTHORIZED_ROLE, GRADE_ROLES, UNAUTHORIZED_ROLE, Grade
from tests.fakes import FakeDiscordMember, FakeGuild

from .conftest import ADMIN_ID, GUILD_ID

COMMAND = "edit_student"


def saved(driver, student):
    return DatabaseController(driver.database_path).find_by_uuid(student.uuid)


def discord_member(user_id: str) -> FakeDiscordMember:
    return FakeDiscordMember(id=int(user_id), guild=FakeGuild(GUILD_ID))


async def edit_and_confirm(driver, **options) -> str:
    """/edit_student を実行して確定し、最後に表示された文章を返す"""
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, **options)
    assert response.view is not None, response.text
    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)
    return confirmed.sent[-1].text


async def test_学籍番号で指定して学年を変えると_学年ロールも変わる(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="ab123456", new_grade=Grade.M1)

    # 確定するまでは何も変わらない
    assert "学年: B4 → M1" in response.embed.description
    assert saved(driver, student).grade == Grade.B4

    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)

    assert "山田 太郎 さんの学生情報を変更しました" in confirmed.sent[-1].text
    assert saved(driver, student).grade == Grade.M1
    assert driver.discord.members["101"].roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}


async def test_メンバーで指定して氏名を変えると_ニックネームも変わる(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")

    await edit_and_confirm(driver, member=discord_member("101"), new_name="山田 次郎")

    assert saved(driver, student).name == "山田 次郎"
    assert driver.discord.members["101"].nickname == "山田 次郎"


async def test_学籍番号とメールアドレスを変えると_新しい値で認証できる(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4)

    await edit_and_confirm(driver, student_number="AB123456", new_student_number="CD654321", new_email="new@shizuoka.ac.jp")

    assert (saved(driver, student).student_number, saved(driver, student).email) == ("CD654321", "new@shizuoka.ac.jp")
    await driver.member_joins("201")
    for text in ["山田 太郎", "CD654321", "B4"]:
        await driver.send_dm("201", text)
    assert "認証コードを送信しました" in await driver.send_dm("201", "new@shizuoka.ac.jp")


async def test_Discordとの紐付けを解除すると未認証に戻り_もう一度認証できる(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")

    await edit_and_confirm(driver, student_number="AB123456", unlink_discord=True)

    assert saved(driver, student).discord_id is None
    assert driver.discord.members["101"].roles == {UNAUTHORIZED_ROLE.name}
    assert "名前 (フルネーム) を教えてください。" in await driver.send_dm("101", "こんにちは")


async def test_未認証の学生は学生情報だけ変わる(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4)

    text = await edit_and_confirm(driver, student_number="AB123456", new_grade=Grade.M1)

    assert saved(driver, student).grade == Grade.M1
    assert "未認証" in text


async def test_キャンセルすると何も変わらない(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456", new_grade=Grade.M1)

    cancelled = driver.component_interaction(ADMIN_ID)
    await response.view.cancel(cancelled)

    assert "キャンセルしました" in cancelled.sent[-1].text
    assert saved(driver, student).grade == Grade.B4
    assert GRADE_ROLES[Grade.B4].name in driver.discord.members["101"].roles


async def test_確認中に学生情報が変わっていたら確定しない(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456", new_grade=Grade.M1)
    await edit_and_confirm(driver, student_number="AB123456", new_name="山田 次郎")  # 別の管理者が先に変更した

    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)

    assert "やり直してください" in confirmed.sent[-1].text
    assert saved(driver, student).grade == Grade.B4


async def test_対象は学籍番号かメンバーのどちらか一方で指定する(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")
    expected = "学籍番号 (student_number) か メンバー (member) のどちらか一方を指定してください。"

    assert await driver.run_command(ADMIN_ID, COMMAND, new_grade=Grade.M1) == expected
    assert (
        await driver.run_command(
            ADMIN_ID, COMMAND, student_number="AB123456", member=discord_member("101"), new_grade=Grade.M1
        )
        == expected
    )


async def test_見つからない学生は変更できない(driver):
    assert await driver.run_command(ADMIN_ID, COMMAND, student_number="ZZ999999", new_grade=Grade.M1) == (
        "学籍番号 ZZ999999 の学生情報が見つかりません。"
    )
    driver.discord.add_member("999")
    assert await driver.run_command(ADMIN_ID, COMMAND, member=discord_member("999"), new_grade=Grade.M1) == (
        "このメンバーに紐付いた学生情報が見つかりません。"
    )


async def test_変更する項目が無ければ知らせる(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    assert await driver.run_command(ADMIN_ID, COMMAND, student_number="AB123456") == "変更する項目を指定してください。"
    assert (
        await driver.run_command(ADMIN_ID, COMMAND, student_number="AB123456", new_grade=Grade.B4)
        == "変更する項目を指定してください。"
    )


async def test_形式が不正な値や重複する値には変更できない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    driver.add_student("鈴木 花子", "CD123456", Grade.M1)

    assert "学籍番号 CD123456 はすでに登録されています" in await driver.run_command(
        ADMIN_ID, COMMAND, student_number="AB123456", new_student_number="CD123456"
    )
    assert "@shizuoka.ac.jp" in await driver.run_command(
        ADMIN_ID, COMMAND, student_number="AB123456", new_email="yamada@gmail.com"
    )


async def test_紐付いていない学生の紐付けは解除できない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    assert await driver.run_command(ADMIN_ID, COMMAND, student_number="AB123456", unlink_discord=True) == (
        "この学生情報は Discord アカウントと紐付いていません。"
    )


async def test_管理者以外は実行できない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    driver.discord.add_member("111")
    reply = await driver.run_command("111", COMMAND, student_number="AB123456", new_grade=Grade.M1)
    assert reply == "このコマンドは管理者のみが使用できます。"


async def test_確認画面は実行した管理者しか操作できない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456", new_grade=Grade.M1)

    assert await response.view.interaction_check(driver.component_interaction(ADMIN_ID))
    assert not await response.view.interaction_check(driver.component_interaction("999"))
