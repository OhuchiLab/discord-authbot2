"""
/health_check コマンド: Bot が動いているかを確認する
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot import AuthBot


def setup_health_check_command(bot: AuthBot) -> None:
    """
    /health_check コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(name="health_check", description="Botの状態を確認します", guild=bot.guild_object)
    async def health_check(interaction: discord.Interaction) -> None:
        # [F1]
        await interaction.response.send_message("I'm alive!", ephemeral=True)
