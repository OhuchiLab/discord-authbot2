"""
Discord Bot 本体 (クライアント) の定義

Discord から届くイベントを、`events` パッケージの各処理へ振り分けます。
"""

import logging

import discord
from discord import app_commands

import commands
import events
from controllers import BotControllers
from utils import BotConfig

logger = logging.getLogger(__name__)


class AuthBot(discord.Client):
    """
    認証 Bot のクライアント

    使い方 (`main.py` と機能テストで共通):

        bot = AuthBot(config)
        bot.controllers = build_controllers(..., discord_gateway=DiscordGateway(bot, config.guild_id), ...)
        bot.run(token)

    コントローラーは Discord の操作に Bot 自身 (DiscordGateway 経由) を使うため、
    Bot を作った後に設定します。

    Attributes:
        config (BotConfig): 設定値
        controllers (BotControllers): コントローラー一式 (Bot の作成後に設定する)
        tree (app_commands.CommandTree): スラッシュコマンドの登録先
        guild_object (discord.Object): Bot を動かすサーバーを表すオブジェクト (コマンド登録に使う)
    """

    controllers: BotControllers

    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        # サーバーへのメンバー参加イベントを受け取るために必要
        # (Discord Developer Portal で "Server Members Intent" を有効にしておくこと)
        intents.members = True
        super().__init__(intents=intents)

        self.config = config
        self.tree = app_commands.CommandTree(self)
        self.guild_object = discord.Object(id=config.guild_id)

    def register_commands(self) -> None:
        """
        スラッシュコマンドを `tree` に登録する (Discord への反映は `setup_hook` で行う)
        """
        commands.setup_all_commands(self)

    async def setup_hook(self) -> None:
        """
        ログイン直後に 1 度だけ呼ばれる。スラッシュコマンドを登録し、Discord に反映する
        """
        self.register_commands()
        synced = await self.tree.sync(guild=self.guild_object)
        logger.info("Synced %d slash commands: %s", len(synced), ", ".join(c.name for c in synced))

    # ------------------------------------------------------------------
    # Discord のイベント → events パッケージの処理へ振り分け
    # ------------------------------------------------------------------

    async def on_ready(self) -> None:
        """Bot の準備が完了したとき"""
        await events.handle_ready(self)

    async def on_member_join(self, member: discord.Member) -> None:
        """サーバーに新しいメンバーが参加したとき"""
        await events.handle_member_join(self, member)

    async def on_message(self, message: discord.Message) -> None:
        """メッセージを受け取ったとき"""
        await events.handle_message(self, message)
