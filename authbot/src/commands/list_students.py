"""
/list_students コマンド: 登録されている学生情報の一覧を表示する (管理者のみ)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands

from .grade_option import GRADE_LABELS, GradeOption
from .list_students_view import StudentListView

if TYPE_CHECKING:
    from bot import AuthBot


def setup_list_students_command(bot: AuthBot) -> None:
    """
    /list_students コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(
        name="list_students",
        description="【管理者用】登録されている学生情報の一覧を表示します。学年や認証の状態で絞り込めます",
        guild=bot.guild_object,
    )
    @app_commands.describe(
        grade="この学年の人だけを表示する (省略すると全学年)",
        status="認証済み / 未認証 の人だけを表示する (省略すると全員)",
    )
    async def list_students(
        interaction: discord.Interaction,
        grade: GradeOption | None = None,
        status: Literal["認証済み", "未認証"] | None = None,
    ) -> None:
        # [F11] 個人情報を含むため、応答はすべて実行者にだけ見える (ephemeral) メッセージにする
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 管理者 (Administrator ロールを持つメンバー) だけが実行できる
        if not await bot.controllers.role.is_admin(str(interaction.user.id)):
            await interaction.followup.send("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        authenticated = None if status is None else status == "認証済み"
        students = bot.controllers.student.list_students(grade=grade, authenticated=authenticated)
        if not students:
            await interaction.followup.send("条件に合う学生はいません。", ephemeral=True)
            return

        filters = []
        if grade is not None:
            filters.append(f"学年: {GRADE_LABELS[grade]}")
        if status is not None:
            filters.append(status)
        view = StudentListView(students, ", ".join(filters), interaction.user.id)

        if view.page_count > 1:
            await interaction.followup.send(embed=view.render(), view=view, ephemeral=True)
        else:
            view.stop()  # 1 ページに収まるならボタンは不要
            await interaction.followup.send(embed=view.render(), ephemeral=True)
