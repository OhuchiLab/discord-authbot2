"""
[機能] F11 学生情報の一覧 (/list_students)

管理者が /list_students を実行すると、登録されている学生情報の一覧が (絞り込み・ページ分けされて) 表示されることを確認します。
"""

from several_types import Grade

from .conftest import ADMIN_ID

COMMAND = "list_students"


async def test_管理者は登録済みの学生の一覧を見られる(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.M1, discord_id="101")
    driver.add_student("鈴木 花子", "CD123456", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)

    assert response.embed.title == "学生一覧"
    text = response.embed.description
    assert "全 2 人 (認証済み 1 人 / 未認証 1 人)" in text
    assert "山田 太郎 | AB123456 | M1 | ab123456@shizuoka.ac.jp | <@101>" in text
    assert "鈴木 花子 | CD123456 | B4 | cd123456@shizuoka.ac.jp | 未認証" in text


async def test_学年順_同じ学年は学籍番号順に並ぶ(driver):
    driver.add_student("OB 太郎", "AA000001", Grade.OBOG)
    driver.add_student("M1 花子", "AA000002", Grade.M1)
    driver.add_student("B4 次郎", "BB000001", Grade.B4)
    driver.add_student("B4 一郎", "AA000003", Grade.B4)

    text = (await driver.run_command_for_response(ADMIN_ID, COMMAND)).embed.description

    positions = [text.index(name) for name in ["B4 一郎", "B4 次郎", "M1 花子", "OB 太郎"]]
    assert positions == sorted(positions)


async def test_学年で絞り込める(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.M1)
    driver.add_student("鈴木 花子", "CD123456", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, grade=Grade.B4)

    assert "鈴木 花子" in response.embed.description
    assert "山田 太郎" not in response.embed.description
    assert "学年: B4" in response.embed.footer.text


async def test_未認証の人だけに絞り込める(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.M1, discord_id="101")
    driver.add_student("鈴木 花子", "CD123456", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, status="未認証")

    assert "鈴木 花子" in response.embed.description
    assert "山田 太郎" not in response.embed.description


async def test_条件に合う学生がいなければ知らせる(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.M1)
    assert await driver.run_command(ADMIN_ID, COMMAND, grade=Grade.D1) == "条件に合う学生はいません。"


async def test_人数が多ければページを切り替えて表示する(driver):
    for i in range(25):
        driver.add_student(f"学生{i:02d}", f"AB0000{i:02d}", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)
    assert "1 / 2 ページ" in response.embed.footer.text
    assert "学生00" in response.embed.description
    assert "学生24" not in response.embed.description

    next_page = driver.component_interaction(ADMIN_ID)
    await response.view.show_page(next_page, 1)
    assert "学生24" in next_page.sent[-1].embed.description
    assert "2 / 2 ページ" in next_page.sent[-1].embed.footer.text


async def test_1ページに収まればボタンを出さない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.M1)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)
    assert response.view is None


async def test_ページ切り替えは実行した管理者しか操作できない(driver):
    for i in range(25):
        driver.add_student(f"学生{i:02d}", f"AB0000{i:02d}", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)

    assert await response.view.interaction_check(driver.component_interaction(ADMIN_ID))
    assert not await response.view.interaction_check(driver.component_interaction("999"))


async def test_管理者以外は実行できない(driver):
    driver.discord.add_member("111")
    assert await driver.run_command("111", COMMAND) == "このコマンドは管理者のみが使用できます。"
