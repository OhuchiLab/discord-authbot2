"""
[機能] F9 現役メンバーの年度更新 (/update_grades)

管理者が /update_grades を実行 → 更新候補を確認・修正 → 確定 すると、
学生情報 (ファイル) が更新され、その内容が Discord の学年ロールに反映されることを確認します。
"""

from datetime import date

from several_types import AUTHORIZED_ROLE, GRADE_ROLES, Grade

from .conftest import ADMIN_ID

COMMAND = "update_grades"


def role_names(driver, discord_id: str) -> set[str]:
    return driver.discord.members[discord_id].roles


async def test_確定すると学生情報と学年ロールが1つ進む(driver):
    b4 = driver.add_student("B4 太郎", "B4000001", Grade.B4, discord_id="101")
    m2 = driver.add_student("M2 花子", "M2000001", Grade.M2, discord_id="102")

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)

    # 確定するまでは何も変わらない
    assert "2027年度" in response.embed.title
    assert "B4 → M1" in response.embed.description
    assert "M2 → OB/OG" in response.embed.description
    assert driver.saved_grade(b4) == Grade.B4

    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)

    assert "更新しました" in confirmed.sent[-1].text
    assert driver.saved_grade(b4) == Grade.M1
    assert driver.saved_grade(m2) == Grade.OBOG
    assert role_names(driver, "101") == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}
    # 卒業・修了: 学年ロールを外して OB/OG ロールを付ける
    assert role_names(driver, "102") == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.OBOG].name}


async def test_留年や進学に変更してから確定できる(driver):
    repeat = driver.add_student("留年 太郎", "B4000001", Grade.B4, discord_id="101")
    doctor = driver.add_student("進学 花子", "M2000001", Grade.M2, discord_id="102")
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)
    view = response.view

    await view.select_student(driver.component_interaction(ADMIN_ID), repeat.uuid)
    changed = driver.component_interaction(ADMIN_ID)
    await view.select_next_grade(changed, Grade.B4)
    await view.select_student(driver.component_interaction(ADMIN_ID), doctor.uuid)
    await view.select_next_grade(driver.component_interaction(ADMIN_ID), Grade.D1)

    assert "B4 → B4 (留年)" in changed.sent[-1].embed.description
    await view.confirm(driver.component_interaction(ADMIN_ID))

    assert driver.saved_grade(repeat) == Grade.B4
    assert driver.saved_grade(doctor) == Grade.D1
    assert GRADE_ROLES[Grade.D1].name in role_names(driver, "102")
    assert GRADE_ROLES[Grade.M2].name not in role_names(driver, "102")


async def test_キャンセルすると学生情報もロールも変わらない(driver):
    student = driver.add_student("B4 太郎", "B4000001", Grade.B4, discord_id="101")
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)

    cancelled = driver.component_interaction(ADMIN_ID)
    await response.view.cancel(cancelled)

    assert "キャンセルしました" in cancelled.sent[-1].text
    assert driver.saved_grade(student) == Grade.B4
    assert role_names(driver, "101") == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.B4].name}
    # キャンセルした年度は、もう一度実行できる
    again = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)
    assert again.view is not None


async def test_同じ年度は二度実行できない(driver):
    student = driver.add_student("B4 太郎", "B4000001", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)
    await response.view.confirm(driver.component_interaction(ADMIN_ID))

    driver.restart_bot()  # 実行済みの年度は再起動しても覚えている
    reply = await driver.run_command(ADMIN_ID, COMMAND, fiscal_year=2027)

    assert reply == "2027年度の現役更新は既に実行されています。"
    assert driver.saved_grade(student) == Grade.M1


async def test_年度を省略すると次の年度になる(driver):
    driver.add_student("B4 太郎", "B4000001", Grade.B4)

    driver.today = date(2026, 9, 24)  # 2026年度の途中
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)
    assert "2027年度" in response.embed.title

    driver.today = date(2027, 4, 1)  # 2027年度の初日
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)
    assert "2028年度" in response.embed.title


async def test_OBOGと教員は対象外(driver):
    driver.add_student("卒業 太郎", "OB000001", Grade.OBOG)
    driver.add_student("教員 花子", "TC000001", Grade.TEACHER)
    driver.add_student("B4 次郎", "B4000001", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)

    assert "B4 次郎" in response.embed.description
    assert "卒業 太郎" not in response.embed.description
    assert "教員 花子" not in response.embed.description


async def test_未認証の学生も学生情報は更新される(driver):
    unauthenticated = driver.add_student("未認証 太郎", "B4000001", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)
    assert "(未認証)" in response.embed.description
    await response.view.confirm(driver.component_interaction(ADMIN_ID))

    assert driver.saved_grade(unauthenticated) == Grade.M1


async def test_管理者以外は実行できない(driver):
    driver.discord.add_member("111")
    reply = await driver.run_command("111", COMMAND, fiscal_year=2027)
    assert reply == "このコマンドは管理者のみが使用できます。"


async def test_確認画面は実行した管理者しか操作できない(driver):
    driver.add_student("B4 太郎", "B4000001", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)

    assert await response.view.interaction_check(driver.component_interaction(ADMIN_ID))
    assert not await response.view.interaction_check(driver.component_interaction("999"))


async def test_対象の学生がいなければ知らせる(driver):
    reply = await driver.run_command(ADMIN_ID, COMMAND, fiscal_year=2027)
    assert reply == "年度更新の対象となる現役メンバーがいません。"


async def test_25人を超えるとページを切り替えて表示する(driver):
    students = [driver.add_student(f"学生{i:02d}", f"B40000{i:02d}", Grade.B4) for i in range(30)]
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, fiscal_year=2027)
    view = response.view

    student_select = view.children[0]
    assert len(student_select.options) == 25  # Discord のセレクトメニューは 25 個まで
    assert "1 / 2 ページ" in response.embed.footer.text

    next_page = driver.component_interaction(ADMIN_ID)
    await view.show_page(next_page, 1)
    assert students[29].name in next_page.sent[-1].embed.description
    assert students[0].name not in next_page.sent[-1].embed.description
