"""
システムテストの共通部品

システムテストは、本物の Discord (テスト用サーバー) と本物の SMTP サーバーを使います。
普段の `pytest` では実行せず、環境変数 RUN_SYSTEM_TESTS=1 のときだけ実行します。

    RUN_SYSTEM_TESTS=1 python -m pytest tests/system

設定はテスト用の .env ファイル (既定: .env.system、AUTHBOT_ENV_FILE で変更可) から読み込みます。
手順の詳細は docs/test_design.md の「システムテスト」を参照してください。
"""

import asyncio
import os
from pathlib import Path

import pytest

from bot import AuthBot
from controllers import build_controllers
from database import DatabaseController
from external import DiscordGateway, MailSender
from utils import BotConfig, load_config

READY_TIMEOUT_SECONDS = 60


@pytest.fixture(autouse=True)
def skip_unless_enabled():
    if os.getenv("RUN_SYSTEM_TESTS") != "1":
        pytest.skip("システムテストは RUN_SYSTEM_TESTS=1 のときだけ実行します")


@pytest.fixture
def config() -> BotConfig:
    return load_config(Path(os.getenv("AUTHBOT_ENV_FILE", ".env.system")))


@pytest.fixture
def mail_sender(config) -> MailSender:
    return MailSender(
        host=config.smtp_host,
        port=config.smtp_port,
        mail_from=config.mail_from,
        user=config.smtp_user,
        password=config.smtp_password,
        use_starttls=config.smtp_use_starttls,
    )


@pytest.fixture
async def running_bot(config, mail_sender, tmp_path):
    """
    本物の Discord にログインした Bot。学生情報は一時フォルダのファイルを使う (本番のファイルには触れない)
    """
    bot = AuthBot(config)
    bot.controllers = build_controllers(
        DatabaseController(tmp_path / "students.msgpack"),
        mail_sender,
        DiscordGateway(bot, config.guild_id),
        config.allowed_email_domain,
    )

    login_task = asyncio.create_task(bot.start(config.discord_token))
    ready_task = asyncio.create_task(bot.wait_until_ready())
    done, _ = await asyncio.wait({login_task, ready_task}, timeout=READY_TIMEOUT_SECONDS, return_when=asyncio.FIRST_COMPLETED)
    if ready_task not in done:
        ready_task.cancel()
        await bot.close()
        if login_task in done:
            login_task.result()  # ログインに失敗した理由を例外として表示する
        pytest.fail(f"{READY_TIMEOUT_SECONDS} 秒以内に Bot の準備が完了しませんでした")

    yield bot

    await bot.close()
    await asyncio.gather(login_task, return_exceptions=True)
