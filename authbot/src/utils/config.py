"""
Bot の設定値を環境変数 (.env ファイル) から読み込む
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """
    必要な設定値が不足している、または不正なときに送出される例外
    """


@dataclass(frozen=True)
class BotConfig:
    """
    Bot の設定値

    各項目に対応する環境変数名は `load_config()` を参照してください。

    Attributes:
        discord_token (str): Discord Bot のトークン
        guild_id (int): Bot を動かす Discord サーバーの ID
        database_path (Path): 学生情報を保存するファイルのパス
        allowed_email_domain (str): 受け付けるメールアドレスのドメイン (例: "shizuoka.ac.jp")
        smtp_host (str): 認証メールを送る SMTP サーバーのホスト名
        smtp_port (int): SMTP サーバーのポート番号
        smtp_use_starttls (bool): STARTTLS で通信を暗号化するかどうか
        smtp_user (str | None): SMTP サーバーのログインユーザー名。None ならログインしない
        smtp_password (str | None): SMTP サーバーのログインパスワード
        mail_from (str): 認証メールの差出人アドレス
    """

    discord_token: str
    guild_id: int
    database_path: Path
    allowed_email_domain: str
    smtp_host: str
    smtp_port: int
    smtp_use_starttls: bool
    smtp_user: str | None
    smtp_password: str | None
    mail_from: str


def load_config(env_file: Path = Path(".env")) -> BotConfig:
    """
    .env ファイルと環境変数から設定値を読み込む

    すでに設定されている環境変数は、.env ファイルの値より優先されます。

    | 環境変数 | 必須 | 既定値 |
    | --- | --- | --- |
    | DISCORD_TOKEN | ○ | |
    | GUILD_ID | ○ | |
    | DATABASE_PATH | | data/students.msgpack |
    | ALLOWED_EMAIL_DOMAIN | | shizuoka.ac.jp |
    | SMTP_HOST | ○ | |
    | SMTP_PORT | | 587 |
    | SMTP_USE_STARTTLS | | true |
    | SMTP_USER | | (ログインしない) |
    | SMTP_PASSWORD | | |
    | MAIL_FROM | SMTP_USER が無ければ ○ | SMTP_USER と同じ |

    Args:
        env_file (Path): 読み込む .env ファイル (無ければ環境変数だけを使う)

    Returns:
        BotConfig: 読み込んだ設定値

    Raises:
        ConfigError: 必須の設定値が無い、または値の形式が不正な場合
    """
    load_dotenv(env_file)

    required_names = ["DISCORD_TOKEN", "GUILD_ID", "SMTP_HOST"]
    missing_names = [name for name in required_names if not os.getenv(name)]
    if not os.getenv("MAIL_FROM") and not os.getenv("SMTP_USER"):
        missing_names.append("MAIL_FROM (または SMTP_USER)")
    if missing_names:
        raise ConfigError(f"必須の環境変数が設定されていません: {', '.join(missing_names)}")

    return BotConfig(
        discord_token=os.environ["DISCORD_TOKEN"],
        guild_id=_read_int("GUILD_ID", os.environ["GUILD_ID"]),
        database_path=Path(os.getenv("DATABASE_PATH") or "data/students.msgpack"),
        allowed_email_domain=os.getenv("ALLOWED_EMAIL_DOMAIN") or "shizuoka.ac.jp",
        smtp_host=os.environ["SMTP_HOST"],
        smtp_port=_read_int("SMTP_PORT", os.getenv("SMTP_PORT") or "587"),
        smtp_use_starttls=_read_bool("SMTP_USE_STARTTLS", os.getenv("SMTP_USE_STARTTLS") or "true"),
        smtp_user=os.getenv("SMTP_USER") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        mail_from=os.getenv("MAIL_FROM") or os.environ["SMTP_USER"],
    )


def _read_int(name: str, value: str) -> int:
    """
    環境変数の値を整数に変換する

    Raises:
        ConfigError: 整数に変換できない場合
    """
    try:
        return int(value)
    except ValueError as error:
        raise ConfigError(f"環境変数 {name} は整数である必要があります: {value!r}") from error


def _read_bool(name: str, value: str) -> bool:
    """
    環境変数の値を真偽値に変換する ("true" / "false"、大文字小文字は区別しない)

    Raises:
        ConfigError: "true" / "false" 以外の場合
    """
    normalized = value.strip().lower()
    if normalized not in ("true", "false"):
        raise ConfigError(f"環境変数 {name} は true または false である必要があります: {value!r}")
    return normalized == "true"
