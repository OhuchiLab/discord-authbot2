"""
Bot の準備完了 (ready) イベントの処理
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import AuthBot

logger = logging.getLogger(__name__)


async def handle_ready(bot: AuthBot) -> None:
    """
    [F8] Bot の準備が完了したときの処理。必要なロールがサーバーに揃っているようにする

    Args:
        bot (AuthBot): Bot 本体
    """
    logger.info("Logged in as %s", bot.user)
    await bot.controllers.role.setup_roles()
    logger.info("Bot is ready")
