"""
[機能] F13 学生情報の書き出し (/export_students)

管理者が /export_students を実行すると、学生情報のファイル (CSV または msgpack) が添付されて届くことを確認します。
"""

import csv
import io

import msgpack

from several_types import Grade

from .conftest import ADMIN_ID

COMMAND = "export_students"


def read_csv(data: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))


async def test_CSVで書き出すと_Excelで開ける形式で全員分が届く(driver):
    yamada = driver.add_student("山田 太郎", "AB123456", Grade.M1, discord_id="101")
    suzuki = driver.add_student("鈴木 花子", "CD123456", Grade.B4)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)

    assert response.file.filename == "students-20270301.csv"
    data = response.file_bytes()
    assert data.startswith("﻿".encode())  # Excel が UTF-8 と判断できるよう BOM を付ける
    assert read_csv(data) == [
        ["氏名", "学籍番号", "学年", "メールアドレス", "Discord ID", "uuid"],
        ["鈴木 花子", "CD123456", "B4", "cd123456@shizuoka.ac.jp", "", suzuki.uuid],
        ["山田 太郎", "AB123456", "M1", "ab123456@shizuoka.ac.jp", "101", yamada.uuid],
    ]
    assert "2 人分" in response.text


async def test_msgpackで書き出すと_そのまま復元に使える学生情報ファイルが届く(driver):
    driver.add_student("山田 太郎", "AB123456", Grade.M1)

    response = await driver.run_command_for_response(ADMIN_ID, COMMAND, format="msgpack")

    assert response.file.filename == "students-20270301.msgpack"
    exported = msgpack.unpackb(response.file_bytes())
    with open(driver.database_path, "rb") as f:
        assert exported == msgpack.unpack(f)


async def test_学生がいなくても見出しだけのCSVを書き出せる(driver):
    response = await driver.run_command_for_response(ADMIN_ID, COMMAND)
    assert read_csv(response.file_bytes()) == [["氏名", "学籍番号", "学年", "メールアドレス", "Discord ID", "uuid"]]


async def test_管理者以外は実行できない(driver):
    driver.discord.add_member("111")
    assert await driver.run_command("111", COMMAND) == "このコマンドは管理者のみが使用できます。"
