"""
機能テストの共通部品

`BotDriver` は、本物の Bot (AuthBot) を Discord にログインさせずに組み立て、
Discord から届くはずの操作 (参加・DM・スラッシュコマンド) を再現します。

| 本物 | 偽物 |
| --- | --- |
| AuthBot, commands, events, controllers, database (一時フォルダのファイル) | DiscordGateway, MailSender, Discord から渡されるオブジェクト |
"""

from pathlib import Path

import pytest

from bot import AuthBot
from controllers import build_controllers
from database import DatabaseController
from several_types import ADMINISTRATOR_ROLE, Grade
from tests.fakes import (
    FakeDiscordGateway,
    FakeDiscordMember,
    FakeDiscordMessage,
    FakeGuild,
    FakeInteraction,
    FakeMailSender,
    FakeUser,
)
from utils import BotConfig

GUILD_ID = 1000
ADMIN_ID = "1"
"""Administrator ロールを持つ管理者の Discord ユーザー ID"""


class BotDriver:
    """
    機能テストから Bot を操作するための道具

    Attributes:
        bot (AuthBot): テスト対象の Bot (本物)
        discord (FakeDiscordGateway): Discord の状態 (ロール・ニックネーム・送った DM)
        mail (FakeMailSender): 送ったメール
        database_path (Path): 学生情報ファイル
    """

    def __init__(self, tmp_path: Path):
        self.database_path = tmp_path / "students.msgpack"
        self.discord = FakeDiscordGateway()
        self.mail = FakeMailSender()
        self.bot = self._build_bot()
        self.discord.add_member(ADMIN_ID, roles=(ADMINISTRATOR_ROLE.name,))

    def _build_bot(self) -> AuthBot:
        """main.py と同じ手順で Bot を組み立てる (Discord とメール送信だけ偽物)"""
        config = BotConfig(
            discord_token="dummy-token",
            guild_id=GUILD_ID,
            database_path=self.database_path,
            allowed_email_domain="shizuoka.ac.jp",
            smtp_host="localhost",
            smtp_port=1025,
            smtp_use_starttls=False,
            smtp_user=None,
            smtp_password=None,
            mail_from="bot@example.com",
        )
        bot = AuthBot(config)
        bot.controllers = build_controllers(
            DatabaseController(config.database_path), self.mail, self.discord, config.allowed_email_domain
        )
        bot.register_commands()
        return bot

    def restart_bot(self) -> None:
        """Bot を再起動する (学生情報ファイルと Discord の状態はそのまま)"""
        self.bot = self._build_bot()

    # ------------------------------------------------------------------
    # Discord から届く操作の再現
    # ------------------------------------------------------------------

    async def bot_becomes_ready(self) -> None:
        await self.bot.on_ready()

    async def member_joins(self, user_id: str, display_name: str = "新メンバー", **member_options) -> None:
        """サーバーにメンバーが参加する (member_options は FakeMemberState の属性)"""
        self.discord.add_member(user_id, **member_options)
        member = FakeDiscordMember(id=int(user_id), display_name=display_name, guild=FakeGuild(GUILD_ID))
        await self.bot.on_member_join(member)

    async def send_dm(self, user_id: str, text: str) -> str:
        """Bot に DM を送り、Bot から最後に届いた DM を返す"""
        await self.bot.on_message(FakeDiscordMessage(author=FakeUser(id=int(user_id)), content=text))
        return self.discord.last_dm(user_id)

    async def post_in_server(self, user_id: str, text: str) -> None:
        """サーバーのチャンネルに投稿する"""
        await self.bot.on_message(
            FakeDiscordMessage(author=FakeUser(id=int(user_id)), content=text, guild=FakeGuild(GUILD_ID))
        )

    async def run_command(self, user_id: str, command_name: str, /, **options) -> str:
        """スラッシュコマンドを実行し、実行者への最後の応答を返す (応答は ephemeral であることも確認する)"""
        command = self.bot.tree.get_command(command_name, guild=self.bot.guild_object)
        assert command is not None, f"/{command_name} が登録されていません"
        interaction = FakeInteraction(FakeUser(id=int(user_id)), FakeGuild(GUILD_ID))
        await command.callback(interaction, **options)
        assert all(response.ephemeral for response in interaction.sent), "応答は実行者だけに見える必要があります"
        return interaction.sent[-1].text

    # ------------------------------------------------------------------
    # よく使う一連の操作
    # ------------------------------------------------------------------

    async def register_yamada(self) -> str:
        """管理者が山田さんを登録する"""
        return await self.run_command(
            ADMIN_ID, "register", name="山田 太郎", student_number="AB123456", grade=Grade.M1, email="yamada@shizuoka.ac.jp"
        )

    async def answer_questions_as_yamada(self, user_id: str) -> str:
        """DM の質問に山田さんとして答え、届いた認証コードを送る。最後に届いた DM を返す"""
        for text in ["山田 太郎", "AB123456", "M1", "yamada@shizuoka.ac.jp"]:
            await self.send_dm(user_id, text)
        return await self.send_dm(user_id, self.mail.last_code())


@pytest.fixture
def driver(tmp_path) -> BotDriver:
    return BotDriver(tmp_path)
