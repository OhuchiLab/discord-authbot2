"""
[API] Discord に登録するスラッシュコマンドの定義のテスト

Bot が起動時に Discord へ送るコマンドの定義 (名前・説明・選択肢) が、Discord の制限と表示の約束事を守っていることを確認します。
(Discord の制限を超えると、起動時のコマンド登録に失敗します)
"""

import pytest

from bot import AuthBot
from controllers import build_controllers
from database import DatabaseController
from tests.fakes import FakeDiscordGateway, FakeMailSender
from utils import BotConfig

MAX_DESCRIPTION_LENGTH = 100
"""Discord の説明文の最大文字数"""


@pytest.fixture
async def command_payloads(tmp_path) -> list[dict]:
    """Discord に送るコマンドの定義 (JSON にする前の辞書)"""
    config = BotConfig("dummy", 1000, tmp_path / "s.msgpack", "shizuoka.ac.jp", "localhost", 25, False, None, None, "a@b")
    bot = AuthBot(config)
    bot.controllers = build_controllers(
        DatabaseController(config.database_path), FakeMailSender(), FakeDiscordGateway(), "shizuoka.ac.jp"
    )
    bot.register_commands()
    return [command.to_dict(bot.tree) for command in bot.tree.get_commands(guild=bot.guild_object)]


def all_descriptions(payloads: list[dict]) -> list[tuple[str, str]]:
    """(どこの説明か, 説明文) の一覧"""
    result = []
    for command in payloads:
        result.append((f"/{command['name']}", command["description"]))
        result += [(f"/{command['name']} {o['name']}", o["description"]) for o in command.get("options", [])]
    return result


def test_登録されるコマンドの一覧(command_payloads):
    assert [c["name"] for c in command_payloads] == ["health_check", "register", "auth", "update_grades", "edit_student"]


def test_説明文はDiscordの上限文字数以内(command_payloads):
    too_long = [(where, len(text)) for where, text in all_descriptions(command_payloads) if len(text) > MAX_DESCRIPTION_LENGTH]
    assert too_long == []


def test_管理者用コマンドは説明でそれとわかる(command_payloads):
    for command in command_payloads:
        if command["name"] in {"register", "update_grades", "edit_student"}:
            assert command["description"].startswith("【管理者用】"), command["name"]


def test_学年の選択肢はわかりやすい名前で表示し_値は学年の文字列(command_payloads):
    register = next(c for c in command_payloads if c["name"] == "register")
    grade = next(o for o in register["options"] if o["name"] == "grade")
    choices = {choice["name"]: choice["value"] for choice in grade["choices"]}
    assert choices["OB/OG (卒業・修了)"] == "OB/OG"
    assert choices["教員 (TEACHER)"] == "TEACHER"
    assert choices["B4"] == "B4"
