"""
Discord API や、メール認証などの外部機能を使用するためのパッケージ。

Bot の外の世界 (Discord・SMTP サーバー) とのやり取りは、すべてこのパッケージを通します。

| モジュール | 内容 |
| --- | --- |
| `discord_gateway` | Discord API の操作 (DM 送信・チャンネルへの投稿・ロールの付け外し・ニックネーム変更) (`DiscordGateway`) |
| `mail_sender` | SMTP による認証コードメールの送信 (`MailSender`) |
"""

from .discord_gateway import (
    ChannelNotFoundError,
    DiscordGateway,
    DiscordOperationError,
    DiscordPermissionError,
    GuildNotFoundError,
    MemberNotFoundError,
)
from .mail_sender import MailSender, MailSendError
