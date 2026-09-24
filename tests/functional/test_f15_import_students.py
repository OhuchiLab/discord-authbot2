"""
[機能] F15 学生情報の一括登録 (/import_students)

管理者が CSV を添付して /import_students を実行 → 登録する人を確認 → 確定 すると、
全員がまとめて登録されることを確認します。1 行でもエラーがあれば、何も登録しません。
"""

from database import DatabaseController
from several_types import Grade
from tests.fakes import FakeAttachment

from .conftest import ADMIN_ID

COMMAND = "import_students"

HEADER = "氏名,学籍番号,学年,メールアドレス\n"


def csv_file(body: str, encoding: str = "utf-8", filename: str = "students.csv") -> FakeAttachment:
    return FakeAttachment(filename, (HEADER + body).encode(encoding))


def saved_names(driver) -> list[str]:
    return [s.name for s in DatabaseController(driver.database_path).get_all()]


async def import_and_confirm(driver, file: FakeAttachment) -> str:
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, file=file)
    assert response.view is not None, response.text
    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)
    return confirmed.sent[-1].text


async def test_CSVの全員を確認してから一括登録できる(driver):
    file = csv_file("山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n鈴木 花子,cd123456,m1,suzuki@shizuoka.ac.jp\n")

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, file=file)

    # 確定するまでは登録しない
    assert "2 人" in response.embed.title
    assert "山田 太郎 | AB123456 | B4 | yamada@shizuoka.ac.jp" in response.embed.description
    assert "鈴木 花子 | CD123456 | M1 | suzuki@shizuoka.ac.jp" in response.embed.description
    assert saved_names(driver) == []

    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)

    assert confirmed.sent[-1].text == "2 人の学生情報を登録しました。"
    assert saved_names(driver) == ["山田 太郎", "鈴木 花子"]


async def test_登録した人はそのまま認証できる(driver):
    await import_and_confirm(driver, csv_file("山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n"))

    await driver.member_joins("101")
    for text in ["山田 太郎", "AB123456", "B4"]:
        await driver.send_dm("101", text)
    assert "認証コードを送信しました" in await driver.send_dm("101", "yamada@shizuoka.ac.jp")


async def test_ExcelのShiftJISのCSVも読める(driver):
    await import_and_confirm(driver, csv_file("山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\r\n", encoding="cp932"))
    assert saved_names(driver) == ["山田 太郎"]


async def test_export_studentsで書き出したCSVの形も読める(driver):
    exported_header = "氏名,学籍番号,学年,メールアドレス,Discord ID,uuid\r\n"
    file = FakeAttachment("students.csv", ("﻿" + exported_header + "山田 太郎,AB123456,OB/OG,yamada@shizuoka.ac.jp,,\r\n").encode())

    await import_and_confirm(driver, file)

    assert [s.grade for s in DatabaseController(driver.database_path).get_all()] == [Grade.OBOG]


async def test_1行でもエラーがあれば全行のエラーを示して何も登録しない(driver):
    driver.add_student("登録済み 太郎", "ZZ000001", Grade.M1)
    file = csv_file(
        "山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n"  # 2 行目: 正しい
        "鈴木 花子,1234,B4,suzuki@shizuoka.ac.jp\n"  # 3 行目: 学籍番号の形式
        "佐藤 次郎,CD123456,B5,sato@shizuoka.ac.jp\n"  # 4 行目: 学年
        "田中 三郎,ZZ000001,B4,tanaka@shizuoka.ac.jp\n"  # 5 行目: 登録済み
        "山田 花子,AB123456,B4,hanako@shizuoka.ac.jp\n"  # 6 行目: CSV の中で重複
    )

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, file=file)

    assert response.view is None
    text = response.text
    assert "何も登録していません" in text
    assert "3 行目: 学籍番号は英数字 8 文字で入力してください。" in text
    assert "4 行目: 学年" in text
    assert "5 行目: 学籍番号 ZZ000001 はすでに登録されています。" in text
    assert "6 行目: 学籍番号 AB123456 が CSV の中で重複しています" in text
    assert not any(line.startswith("2 行目:") for line in text.splitlines())  # 正しい行はエラーにしない
    assert saved_names(driver) == ["登録済み 太郎"]


async def test_必要な列が無いCSVは読まない(driver):
    file = FakeAttachment("students.csv", "氏名,学籍番号\n山田 太郎,AB123456\n".encode())
    reply = await driver.run_command(ADMIN_ID, COMMAND, file=file)
    assert reply == "CSV の 1 行目に、次の列がありません: 学年, メールアドレス"


async def test_CSV以外のファイルは読まない(driver):
    reply = await driver.run_command(ADMIN_ID, COMMAND, file=FakeAttachment("students.xlsx", b"PK\x03\x04"))
    assert reply == "CSV ファイル (拡張子 .csv) を添付してください。"


async def test_キャンセルすると何も登録しない(driver):
    response = await driver.run_command_for_response(
        ADMIN_ID, COMMAND, file=csv_file("山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n")
    )

    cancelled = driver.component_interaction(ADMIN_ID)
    await response.view.cancel(cancelled)

    assert "キャンセルしました" in cancelled.sent[-1].text
    assert saved_names(driver) == []


async def test_確認中に同じ学生が登録されたら何も登録しない(driver):
    response = await driver.run_command_for_response(
        ADMIN_ID,
        COMMAND,
        file=csv_file("山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n鈴木 花子,CD123456,M1,suzuki@shizuoka.ac.jp\n"),
    )
    driver.add_student("山田 太郎", "AB123456", Grade.B4)  # 別の管理者が先に登録した

    confirmed = driver.component_interaction(ADMIN_ID)
    await response.view.confirm(confirmed)

    assert "やり直してください" in confirmed.sent[-1].text
    assert saved_names(driver) == ["山田 太郎"]


async def test_一括登録ではバックアップを1つだけ作る(driver):
    body = "".join(f"学生{i:02d},AB0000{i:02d},B4,s{i:02d}@shizuoka.ac.jp\n" for i in range(10))
    await import_and_confirm(driver, csv_file(body))
    assert len(list(driver.backup_dir.glob("students-*.msgpack"))) == 1


async def test_管理者以外は実行できない(driver):
    driver.discord.add_member("111")
    reply = await driver.run_command("111", COMMAND, file=csv_file("山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n"))
    assert reply == "このコマンドは管理者のみが使用できます。"


async def test_確認画面は実行した管理者しか操作できない(driver):
    response = await driver.run_command_for_response(
        ADMIN_ID, COMMAND, file=csv_file("山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n")
    )
    assert await response.view.interaction_check(driver.component_interaction(ADMIN_ID))
    assert not await response.view.interaction_check(driver.component_interaction("999"))


async def test_エラーが多くても長くてもDiscordに送れる長さで示す(driver):
    body = "".join(f"学生{i:02d},AB0000{i:02d},{'X' * 300},s{i:02d}@shizuoka.ac.jp\n" for i in range(30))

    reply = await driver.run_command(ADMIN_ID, COMMAND, file=csv_file(body))

    assert len(reply) <= 2000
    assert reply.startswith("CSV に問題があるため、何も登録していません。")
