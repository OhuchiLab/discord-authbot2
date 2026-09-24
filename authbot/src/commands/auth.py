"""
/auth コマンド: 認証手続きを (再) 開始する

参加時の DM を見逃した人や、途中でやめてしまった人のためのコマンドです。
すでに認証済みの人が実行した場合は、ロールとニックネームを付け直します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot import AuthBot


def setup_auth_command(bot: AuthBot) -> None:
    """
    /auth コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(name="auth", description="メンバー認証を開始します (DMで質問が届きます)", guild=bot.guild_object)
    async def auth(interaction: discord.Interaction) -> None:
        # [F6] ロールの付け直しには時間がかかることがあるため、先に「考え中」の表示にしておく
        await interaction.response.defer(ephemeral=True, thinking=True)
        reply_text = await bot.controllers.onboarding.request_auth(str(interaction.user.id))
        await interaction.followup.send(reply_text, ephemeral=True)
