"""
テストで使う偽物 (テストダブル)

| モジュール | 偽物にする対象 | 主に使うテスト |
| --- | --- | --- |
| `fake_discord_gateway` | `external.DiscordGateway` (Discord API) | 単体・API・機能 |
| `fake_mail_sender` | `external.MailSender` (SMTP) | 単体・API・機能 |
| `in_memory_database` | `database.DatabaseController` (ファイル) | 単体 |
| `fake_clock` | 現在時刻 | 単体 |
| `discord_inputs` | Discord から渡されるメンバー・メッセージ・インタラクション・添付ファイル | 機能 |
"""

from .discord_inputs import (
    FakeAttachment,
    FakeDiscordMember,
    FakeDiscordMessage,
    FakeGuild,
    FakeInteraction,
    FakeUser,
    SentResponse,
)
from .fake_clock import FakeClock
from .fake_discord_gateway import FakeDiscordGateway, FakeMemberState
from .fake_mail_sender import FakeMailSender, SentMail
from .in_memory_database import InMemoryDatabase
