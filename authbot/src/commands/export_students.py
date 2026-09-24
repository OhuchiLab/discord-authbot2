"""
/export_students コマンド: 学生情報をファイルに書き出して、実行した管理者に渡す (管理者のみ)
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands

if TYPE_CHECKING:
    from bot import AuthBot

logger = logging.getLogger(__name__)


def setup_export_students_command(bot: AuthBot) -> None:
    """
    /export_students コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(
        name="export_students",
        description="【管理者用】学生情報をファイルに書き出します。CSV は Excel で開け、msgpack は復元に使えます",
        guild=bot.guild_object,
    )
    @app_commands.describe(format="ファイルの形式 (省略すると CSV)")
    async def export_students(
        interaction: discord.Interaction,
        format: Literal["CSV", "msgpack"] = "CSV",  # noqa: A002 (Discord に表示するオプション名として format を使う)
    ) -> None:
        # [F13] 個人情報を含むため、応答はすべて実行者にだけ見える (ephemeral) メッセージにする
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 管理者 (Administrator ロールを持つメンバー) だけが実行できる
        if not await bot.controllers.role.is_admin(str(interaction.user.id)):
            await interaction.followup.send("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        if format == "msgpack":
            exported = bot.controllers.export.export_msgpack()
        else:
            exported = bot.controllers.export.export_csv()

        # 個人情報を持ち出す操作なので、誰がいつ書き出したかを記録する
        logger.info("User %s exported %d students as %s", interaction.user.id, exported.student_count, format)
        await bot.controllers.audit.students_exported(str(interaction.user.id), exported, format)
        await interaction.followup.send(
            f"{exported.student_count} 人分の学生情報を書き出しました。個人情報を含むため、取り扱いに注意してください。",
            file=discord.File(io.BytesIO(exported.data), filename=exported.filename),
            ephemeral=True,
        )
