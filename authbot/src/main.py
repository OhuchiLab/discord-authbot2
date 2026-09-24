"""
メインエントリ: 設定を読み込み、各部品を組み立てて Bot を起動する

部品の組み立て順:

    1. 設定 (BotConfig)
    2. Bot 本体 (AuthBot)
    3. 外部とのやり取り: データベース (DatabaseController) / メール送信 (MailSender) / Discord 操作 (DiscordGateway ← Bot を使う)
    4. コントローラー一式 (build_controllers) → Bot に設定
    5. Bot を起動
"""

import logging
import os
import sys
from pathlib import Path

from bot import AuthBot
from controllers import build_controllers
from database import DatabaseController
from external import DiscordGateway, MailSender
from utils import ConfigError, load_config

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Bot を起動する。Bot が停止するまで戻らない
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # 読み込む .env ファイルは AUTHBOT_ENV_FILE で変更できる (例: システムテスト用の .env.system)
    env_file = Path(os.getenv("AUTHBOT_ENV_FILE", ".env"))
    try:
        config = load_config(env_file)
    except ConfigError as error:
        logger.error("%s (.env.example を参考に .env を作成してください)", error)
        sys.exit(1)

    bot = AuthBot(config)

    database = DatabaseController(config.database_path)
    logger.info("Loaded %d students from %s", len(database.get_all()), config.database_path)
    mail_sender = MailSender(
        host=config.smtp_host,
        port=config.smtp_port,
        mail_from=config.mail_from,
        user=config.smtp_user,
        password=config.smtp_password,
        use_starttls=config.smtp_use_starttls,
    )
    discord_gateway = DiscordGateway(bot, config.guild_id)

    bot.controllers = build_controllers(database, mail_sender, discord_gateway, config.allowed_email_domain)

    # ログの設定は上の basicConfig で済ませているため、discord.py 側の設定は行わない (log_handler=None)
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
