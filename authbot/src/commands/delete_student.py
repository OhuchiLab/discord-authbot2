"""
/delete_student コマンド: 管理者が特定の学生情報を削除する

このコマンドは削除する内容を表示するだけです。
学生情報と Discord は、確認画面 (`delete_student_view.StudentDeleteView`) で「削除する」を押したときに変更されます。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from controllers import StudentDeleteError

from .delete_student_view import StudentDeleteView

if TYPE_CHECKING:
    from bot import AuthBot


def setup_delete_student_command(bot: AuthBot) -> None:
    """
    /delete_student コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(
        name="delete_student",
        description="【管理者用】1 人分の学生情報を削除します。student_number か member で対象を選んでください",
        guild=bot.guild_object,
    )
    @app_commands.describe(
        student_number="対象の人を学籍番号で選ぶ (member を使うなら不要)",
        member="対象の人を Discord で選ぶ (認証済みの人のみ。student_number を使うなら不要)",
    )
    async def delete_student(
        interaction: discord.Interaction,
        student_number: str | None = None,
        member: discord.Member | None = None,
    ) -> None:
        # [F12] 個人情報を含むため、応答はすべて実行者にだけ見える (ephemeral) メッセージにする
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 管理者 (Administrator ロールを持つメンバー) だけが実行できる
        if not await bot.controllers.role.is_admin(str(interaction.user.id)):
            await interaction.followup.send("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        try:
            student = bot.controllers.student_delete.prepare(
                student_number=student_number,
                discord_id=str(member.id) if member is not None else None,
            )
        except StudentDeleteError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        view = StudentDeleteView(
            bot.controllers.student_delete, bot.controllers.audit, student, interaction.user.id, interaction
        )
        await interaction.followup.send(embed=view.render(), view=view, ephemeral=True)
