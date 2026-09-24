"""
サーバーへのメンバー参加 (member join) イベントの処理
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot import AuthBot


async def handle_member_join(bot: AuthBot, member: discord.Member) -> None:
    """
    [F3 / F7] サーバーに新しいメンバーが参加したときの処理

    Bot 自身や、対象外のサーバーへの参加は無視します。
    処理の中身は `controllers.OnboardingController.welcome_new_member()` を参照してください。

    Args:
        bot (AuthBot): Bot 本体
        member (discord.Member): 参加したメンバー
    """
    if member.bot or member.guild.id != bot.config.guild_id:
        return
    await bot.controllers.onboarding.welcome_new_member(str(member.id), member.display_name)
