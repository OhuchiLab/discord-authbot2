"""
[単体] utils.config のテスト

.env ファイルは一時フォルダに作り、環境変数は monkeypatch で設定します。
"""

from pathlib import Path

import pytest

from utils import ConfigError, load_config

ALL_NAMES = [
    "DISCORD_TOKEN",
    "GUILD_ID",
    "DATABASE_PATH",
    "ALLOWED_EMAIL_DOMAIN",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USE_STARTTLS",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "MAIL_FROM",
    "BACKUP_DIR",
    "BACKUP_KEEP",
    "LOG_CHANNEL_NAME",
]


@pytest.fixture(autouse=True)
def clear_environment(monkeypatch):
    """実行環境の環境変数がテストに影響しないよう、関係する環境変数を消す"""
    for name in ALL_NAMES:
        monkeypatch.delenv(name, raising=False)


def write_env(tmp_path: Path, text: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(text, encoding="utf-8")
    return env_file


def test_必須項目だけでも既定値で読み込める(tmp_path):
    env_file = write_env(tmp_path, "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=smtp.example.com\nSMTP_USER=bot@example.com\n")

    config = load_config(env_file)

    assert config.guild_id == 1000
    assert config.database_path == Path("data/students.msgpack")
    assert config.allowed_email_domain == "shizuoka.ac.jp"
    assert config.smtp_port == 587
    assert config.smtp_use_starttls is True
    assert config.smtp_password is None
    assert config.mail_from == "bot@example.com"


def test_ログインしないSMTPサーバーを設定できる(tmp_path):
    env_file = write_env(
        tmp_path,
        "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=localhost\nSMTP_PORT=1025\n"
        "SMTP_USE_STARTTLS=false\nMAIL_FROM=bot@example.com\n",
    )

    config = load_config(env_file)

    assert config.smtp_user is None
    assert config.smtp_use_starttls is False


def test_環境変数は_envファイルより優先する(tmp_path, monkeypatch):
    env_file = write_env(tmp_path, "DISCORD_TOKEN=from-file\nGUILD_ID=1000\nSMTP_HOST=h\nMAIL_FROM=a@example.com\n")
    monkeypatch.setenv("DISCORD_TOKEN", "from-env")
    assert load_config(env_file).discord_token == "from-env"


def test_必須項目が無ければ不足している項目名を示す(tmp_path):
    with pytest.raises(ConfigError, match="DISCORD_TOKEN, GUILD_ID, SMTP_HOST, MAIL_FROM"):
        load_config(tmp_path / "no-such.env")


@pytest.mark.parametrize(("name", "value"), [("GUILD_ID", "abc"), ("SMTP_PORT", "abc"), ("SMTP_USE_STARTTLS", "yes")])
def test_形式が不正な値はエラー(tmp_path, monkeypatch, name, value):
    env_file = write_env(tmp_path, "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=h\nMAIL_FROM=a@example.com\n")
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError, match=name):
        load_config(env_file)


def test_バックアップの設定は既定値を持つ(tmp_path):
    env_file = write_env(tmp_path, "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=h\nMAIL_FROM=a@example.com\n")
    config = load_config(env_file)
    assert (config.backup_dir, config.backup_keep) == (Path("data/backups"), 50)


def test_バックアップの設定を変えられる(tmp_path):
    env_file = write_env(
        tmp_path,
        "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=h\nMAIL_FROM=a@example.com\n"
        "BACKUP_DIR=/mnt/nas/authbot\nBACKUP_KEEP=0\n",
    )
    config = load_config(env_file)
    assert (config.backup_dir, config.backup_keep) == (Path("/mnt/nas/authbot"), 0)


def test_残すバックアップの数が負ならエラー(tmp_path, monkeypatch):
    env_file = write_env(tmp_path, "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=h\nMAIL_FROM=a@example.com\n")
    monkeypatch.setenv("BACKUP_KEEP", "-1")
    with pytest.raises(ConfigError, match="BACKUP_KEEP"):
        load_config(env_file)


def test_ログ用チャンネルの既定はauthbot_logs(tmp_path):
    env_file = write_env(tmp_path, "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=h\nMAIL_FROM=a@example.com\n")
    assert load_config(env_file).log_channel_name == "authbot-logs"


def test_ログ用チャンネルを空にすると投稿しない(tmp_path):
    env_file = write_env(
        tmp_path, "DISCORD_TOKEN=token\nGUILD_ID=1000\nSMTP_HOST=h\nMAIL_FROM=a@example.com\nLOG_CHANNEL_NAME=\n"
    )
    assert load_config(env_file).log_channel_name is None
