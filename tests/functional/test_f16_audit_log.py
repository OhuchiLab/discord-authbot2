"""
[機能] F16 変更履歴のログ用チャンネルへの投稿

管理者の操作 (登録・一括登録・変更・削除・年度更新・書き出し)、メンバーの認証完了、Bot の起動が、
ログ用チャンネル (authbot-logs) に「誰が・何を・どう変えたか」の形で投稿されることを確認します。
"""

from several_types import Grade
from tests.fakes import FakeAttachment

from .conftest import ADMIN_ID

ADMIN = f"<@{ADMIN_ID}>"


async def confirm(driver, command: str, **options) -> None:
    """確認画面のあるコマンドを実行して確定する"""
    response = await driver.run_command_for_response(ADMIN_ID, command, **options)
    assert response.view is not None, response.text
    await response.view.confirm(driver.component_interaction(ADMIN_ID))


async def test_登録を記録する(driver):
    await driver.run_command(
        ADMIN_ID, "register", name="山田 太郎", student_number="AB123456", grade=Grade.B4, email="yamada@shizuoka.ac.jp"
    )

    log = driver.logs()[-1]
    assert "学生情報の登録" in log
    assert ADMIN in log
    assert "山田 太郎 (AB123456)" in log
    assert "B4" in log


async def test_一括登録を記録する(driver):
    csv = "氏名,学籍番号,学年,メールアドレス\n山田 太郎,AB123456,B4,a@shizuoka.ac.jp\n鈴木 花子,CD123456,M1,b@shizuoka.ac.jp\n"
    await confirm(driver, "import_students", file=FakeAttachment("s.csv", csv.encode()))

    log = driver.logs()[-1]
    assert "一括登録" in log and "2 人" in log and ADMIN in log
    assert "山田 太郎 (AB123456)" in log and "鈴木 花子 (CD123456)" in log


async def test_変更を変更前後付きで記録する(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")

    await confirm(driver, "edit_student", student_number="AB123456", new_grade=Grade.M1, new_name="山田 次郎")

    log = driver.logs()[-1]
    assert "学生情報の変更" in log and ADMIN in log
    assert "山田 太郎 (AB123456)" in log
    assert "学年: B4 → M1" in log
    assert "氏名: 山田 太郎 → 山田 次郎" in log


async def test_削除を記録する(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4, discord_id="101")

    await confirm(driver, "delete_student", student_number="AB123456")

    log = driver.logs()[-1]
    assert "学生情報の削除" in log and ADMIN in log
    assert "山田 太郎 (AB123456)" in log
    assert "<@101>" in log  # 未認証に戻したアカウント


async def test_年度更新を記録する(driver):
    repeat = driver.add_student("留年 太郎", "AB000001", Grade.B4)
    driver.add_student("進級 花子", "AB000002", Grade.M1)
    response = await driver.run_command_for_response(ADMIN_ID, "update_grades", fiscal_year=2027)
    await response.view.select_student(driver.component_interaction(ADMIN_ID), repeat.uuid)
    await response.view.select_next_grade(driver.component_interaction(ADMIN_ID), Grade.B4)
    await response.view.confirm(driver.component_interaction(ADMIN_ID))

    log = "\n".join(driver.logs())
    assert "2027年度の現役更新" in log and ADMIN in log
    assert "留年 太郎 (AB000001): B4 → B4 (留年)" in log
    assert "進級 花子 (AB000002): M1 → M2" in log


async def test_書き出しを記録する(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)

    await driver.run_command(ADMIN_ID, "export_students", format="msgpack")

    log = driver.logs()[-1]
    assert "書き出し" in log and ADMIN in log and "msgpack" in log and "1 人分" in log


async def test_メンバーの認証完了を記録する(driver):
    await driver.register_yamada()
    await driver.member_joins("201")

    await driver.answer_questions_as_yamada("201")

    log = driver.logs()[-1]
    assert "認証" in log and "<@201>" in log and "山田 太郎 (AB123456)" in log


async def test_Botの起動を記録する(driver):
    await driver.bot_becomes_ready()
    assert "起動しました" in driver.logs()[-1]


async def test_キャンセルした操作は記録しない(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.B4)
    response = await driver.run_command_for_response(ADMIN_ID, "delete_student", student_number="AB123456")
    await response.view.cancel(driver.component_interaction(ADMIN_ID))

    assert driver.logs() == []


async def test_ログ用チャンネルが無くても操作は成功する(driver):
    del driver.discord.channels[driver.log_channel_name]

    reply = await driver.run_command(
        ADMIN_ID, "register", name="山田 太郎", student_number="AB123456", grade=Grade.B4, email="yamada@shizuoka.ac.jp"
    )

    assert "登録しました" in reply


async def test_ログ用チャンネルに投稿する権限が無くても操作は成功する(driver):
    driver.discord.can_post_to_channels = False

    reply = await driver.run_command(
        ADMIN_ID, "register", name="山田 太郎", student_number="AB123456", grade=Grade.B4, email="yamada@shizuoka.ac.jp"
    )

    assert "登録しました" in reply
