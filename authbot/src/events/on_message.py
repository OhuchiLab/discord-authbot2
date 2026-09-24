"""
メッセージ受信 (message) イベントの処理
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot import AuthBot


async def handle_message(bot: AuthBot, message: discord.Message) -> None:
    """
    [F4 / F5] メッセージを受け取ったときの処理

    Bot 宛ての DM だけを認証手続きに渡します。サーバー内のメッセージや Bot のメッセージは無視します。
    処理の中身は `controllers.OnboardingController.receive_direct_message()` を参照してください。

    Args:
        bot (AuthBot): Bot 本体
        message (discord.Message): 受け取ったメッセージ
    """
    is_direct_message = message.guild is None
    if message.author.bot or not is_direct_message:
        return
    await bot.controllers.onboarding.receive_direct_message(str(message.author.id), message.content)
