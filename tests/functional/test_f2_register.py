"""
[機能] F2 学生情報の登録 (/register)
"""

from database import DatabaseController
from several_types import Grade

from .conftest import ADMIN_ID


async def test_管理者は学生情報を登録でき_ファイルに保存される(driver):
    reply = await driver.register_yamada()

    assert "山田 太郎 さんを登録しました" in reply
    students = DatabaseController(driver.database_path).get_all()
    assert [(s.name, s.student_number, s.grade, s.email) for s in students] == [
        ("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    ]


async def test_管理者以外は登録できない(driver):
    driver.discord.add_member("111")

    reply = await driver.run_command(
        "111", "register", name="山田 太郎", student_number="AB123456", grade=Grade.M1, email="yamada@shizuoka.ac.jp"
    )

    assert reply == "このコマンドは管理者のみが使用できます。"
    assert DatabaseController(driver.database_path).get_all() == []


async def test_形式が不正なら理由を返して登録しない(driver):
    reply = await driver.run_command(
        ADMIN_ID, "register", name="山田 太郎", student_number="AB123456", grade=Grade.M1, email="yamada@gmail.com"
    )
    assert reply.startswith("登録できませんでした: メールアドレスは @shizuoka.ac.jp")


async def test_同じ学籍番号は二重に登録できない(driver):
    await driver.register_yamada()
    reply = await driver.register_yamada()
    assert "すでに登録されています" in reply
