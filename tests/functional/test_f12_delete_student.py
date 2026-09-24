"""
[機能] F12 学生情報の削除 (/delete_student)

管理者が /delete_student で学生を指定 → 削除する内容を確認 → 確定 すると、
学生情報 (ファイル) から削除され、認証済みの学生なら Discord 上で未認証の状態に戻ることを確認します。
"""

from database import DatabaseController
from several_types import UNAUTHORIZED_ROLE, Grade
from tests.fakes import FakeDiscordMember, FakeGuild

from .conftest import ADMIN_ID, GUILD_ID

COMMAND = "delete_student"


def saved(driver, student):
    return DatabaseController(driver.database_path).find_by_uuid(student.uuid)


def discord_member(user_id: str) -> FakeDiscordMember:
    return FakeDiscordMember(id=int(user_id), guild=FakeGuild(GUILD_ID))


async def delete_and_confirm(driver, **options) -> str:
    """/delete_student を実行して確定し、最後に表示された文章を返す"""
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, **options)
    assert response.view is not None, response.text
    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)
    return confirmed.sent[-1].text


async def test_学籍番号で指定して削除できる(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="ab123456")

    # 確定するまでは削除しない
    assert "山田 太郎" in response.embed.description
    assert "AB123456" in response.embed.description
    assert "取り消せません" in response.embed.description
    assert saved(driver, student) is not None

    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)

    assert "山田 太郎 さんの学生情報を削除しました。" in confirmed.sent[-1].text
    assert saved(driver, student) is None


async def test_認証済みの学生を削除すると未認証に戻り_元の情報では認証できない(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")

    text = await delete_and_confirm(driver, member=discord_member("101"))

    assert saved(driver, student) is None
    assert "未認証の状態に戻しました" in text
    assert driver.discord.members["101"].roles == {UNAUTHORIZED_ROLE.name}
    # 本人が DM を送ると手続きが始まるが、元の情報はもう登録されていない
    for message in ["こんにちは", "山田 太郎", "AB123456", "B4"]:
        await driver.send_dm("101", message)
    assert "一致しませんでした" in await driver.send_dm("101", "ab123456@shizuoka.ac.jp")


async def test_削除した学籍番号とメールアドレスはもう一度登録できる(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    await delete_and_confirm(driver, student_number="AB123456")

    reply = await driver.run_command(
        ADMIN_ID, "register", name="山田 太郎", student_number="AB123456", grade=Grade.M1, email="ab123456@shizuoka.ac.jp"
    )
    assert "登録しました" in reply


async def test_サーバーにいない認証済みの学生も削除できる(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")
    del driver.discord.members["101"]

    text = await delete_and_confirm(driver, student_number="AB123456")

    assert saved(driver, student) is None
    assert "サーバーにいない" in text


async def test_キャンセルすると何も変わらない(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")
    roles_before = set(driver.discord.members["101"].roles)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456")

    cancelled = driver.component_interaction(ADMIN_ID)
    await response.view.cancel(cancelled)

    assert "キャンセルしました" in cancelled.sent[-1].text
    assert saved(driver, student) == student
    assert driver.discord.members["101"].roles == roles_before


async def test_確認中に学生情報が変わっていたら削除しない(driver):
    student = driver.add_student("山田 太郎", "AB123456", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456")
    edit = await driver.run_command_for_response(ADMIN_ID, "edit_student", student_number="AB123456", new_grade=Grade.M1)
    await edit.view.confirm(driver.component_interaction(ADMIN_ID))  # 別の管理者が先に変更した

    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)

    assert "やり直してください" in confirmed.sent[-1].text
    assert saved(driver, student) is not None


async def test_確認中に他の管理者が削除していたら知らせる(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    first = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456")
    second = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456")
    await first.view.confirm(driver.component_interaction(ADMIN_ID))

    confirmed = driver.component_interaction(ADMIN_ID)
    await second.view.confirm(confirmed)

    assert "やり直してください" in confirmed.sent[-1].text


async def test_対象は学籍番号かメンバーのどちらか一方で指定する(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")
    expected = "学籍番号 (student_number) か メンバー (member) のどちらか一方を指定してください。"

    assert await driver.run_command(ADMIN_ID, COMMAND) == expected
    assert await driver.run_command(ADMIN_ID, COMMAND, student_number="AB123456", member=discord_member("101")) == expected


async def test_見つからない学生は削除できない(driver):
    assert await driver.run_command(ADMIN_ID, COMMAND, student_number="ZZ999999") == (
        "学籍番号 ZZ999999 の学生情報が見つかりません。"
    )


async def test_管理者以外は実行できない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    driver.discord.add_member("111")
    assert await driver.run_command("111", COMMAND, student_number="AB123456") == "このコマンドは管理者のみが使用できます。"


async def test_確認画面は実行した管理者しか操作できない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, student_number="AB123456")

    assert await response.view.interaction_check(driver.component_interaction(ADMIN_ID))
    assert not await response.view.interaction_check(driver.component_interaction("999"))
