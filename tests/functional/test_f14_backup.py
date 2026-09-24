"""
[機能] F14 学生情報ファイルの自動バックアップ

学生情報を変更するたび (と Bot の起動時) に日時付きのコピーが残り、
そのコピーから学生情報を復元できることを確認します。
"""

import shutil

from database import DatabaseController
from several_types import Grade

from .conftest import ADMIN_ID


def backups(driver) -> list:
    return sorted(driver.backup_dir.glob("students-*.msgpack"))


async def register(driver, name: str, student_number: str) -> str:
    return await driver.run_command(
        ADMIN_ID,
        "register",
        name=name,
        student_number=student_number,
        grade=Grade.B4,
        email=f"{student_number.lower()}@shizuoka.ac.jp",
    )


async def test_学生情報を変更するたびにバックアップが残る(driver):
    await register(driver, "山田 太郎", "AB123456")
    await register(driver, "鈴木 花子", "CD123456")

    files = backups(driver)
    assert len(files) == 2
    assert [s.name for s in DatabaseController(files[0]).get_all()] == ["山田 太郎"]
    assert [s.name for s in DatabaseController(files[1]).get_all()] == ["山田 太郎", "鈴木 花子"]


async def test_起動時にもバックアップを取る(driver):
    await register(driver, "山田 太郎", "AB123456")

    driver.restart_bot()

    assert len(backups(driver)) == 2


async def test_古いバックアップは決められた数だけ残して消す(driver):
    driver.backup_keep = 3
    driver.restart_bot()

    for i in range(5):
        await register(driver, f"学生{i}", f"AB00000{i}")

    files = backups(driver)
    assert len(files) == 3
    assert len(DatabaseController(files[-1]).get_all()) == 5  # 最新のものが残っている


async def test_バックアップから復元できる(driver):
    await register(driver, "山田 太郎", "AB123456")
    backup_with_yamada = backups(driver)[-1]
    await register(driver, "鈴木 花子", "CD123456")

    # 詳細設計書の復元手順: Bot を止めて、バックアップを学生情報ファイルに上書きし、起動する
    shutil.copy(backup_with_yamada, driver.database_path)
    driver.restart_bot()

    assert [s.name for s in driver.bot.controllers.student.list_students()] == ["山田 太郎"]
