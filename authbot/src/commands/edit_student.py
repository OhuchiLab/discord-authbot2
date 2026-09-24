"""
/edit_student コマンド: 管理者が特定の学生情報を手動で変更する

このコマンドは変更前後を表示するだけです。
学生情報と Discord は、確認画面 (`edit_student_view.StudentEditView`) で「確定する」を押したときに変更されます。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from controllers import StudentEditError

from .edit_student_view import StudentEditView
from .grade_option import GradeOption

if TYPE_CHECKING:
    from bot import AuthBot


def setup_edit_student_command(bot: AuthBot) -> None:
    """
    /edit_student コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(
        name="edit_student",
        description="【管理者用】1 人分の学生情報を変更します。student_number か member で対象を選んでください",
        guild=bot.guild_object,
    )
    @app_commands.describe(
        student_number="対象の人を学籍番号で選ぶ (member を使うなら不要)",
        member="対象の人を Discord で選ぶ (認証済みの人のみ。student_number を使うなら不要)",
        new_name="変更後の氏名 (ニックネームも変わります)",
        new_student_number="変更後の学籍番号 (英数字 8 文字)",
        new_grade="変更後の学年 (学年ロールも変わります)",
        new_email="変更後の大学メールアドレス",
        unlink_discord="「True」を選ぶと、この人の Discord アカウントの認証を取り消します (再認証が必要になります)",
    )
    async def edit_student(
        interaction: discord.Interaction,
        student_number: str | None = None,
        member: discord.Member | None = None,
        new_name: str | None = None,
        new_student_number: str | None = None,
        new_grade: GradeOption | None = None,
        new_email: str | None = None,
        unlink_discord: bool = False,
    ) -> None:
        # [F10] 個人情報を含むため、応答はすべて実行者にだけ見える (ephemeral) メッセージにする
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 管理者 (Administrator ロールを持つメンバー) だけが実行できる
        if not await bot.controllers.role.is_admin(str(interaction.user.id)):
            await interaction.followup.send("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        try:
            edit = bot.controllers.student_edit.prepare(
                student_number=student_number,
                discord_id=str(member.id) if member is not None else None,
                new_name=new_name,
                new_student_number=new_student_number,
                new_grade=new_grade,
                new_email=new_email,
                unlink_discord=unlink_discord,
            )
        except StudentEditError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        view = StudentEditView(bot.controllers.student_edit, bot.controllers.audit, edit, interaction.user.id, interaction)
        await interaction.followup.send(embed=view.render(), view=view, ephemeral=True)
