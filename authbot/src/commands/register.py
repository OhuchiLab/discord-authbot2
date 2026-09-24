"""
/register コマンド: 管理者が新しいメンバーの学生情報を登録する
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from controllers import StudentRegistrationError

from .grade_option import GradeOption

if TYPE_CHECKING:
    from bot import AuthBot

logger = logging.getLogger(__name__)


def setup_register_command(bot: AuthBot) -> None:
    """
    /register コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(
        name="register",
        description="【管理者用】研究室メンバーの情報を登録します。登録された人だけが認証できます",
        guild=bot.guild_object,
    )
    @app_commands.describe(
        name="氏名 (例: 山田 太郎)。本人が認証時に入力する氏名と照合します",
        student_number="学籍番号 (英数字 8 文字)",
        grade="今の学年",
        email="大学のメールアドレス (例: yamada.taro.21@shizuoka.ac.jp)。認証コードの送信先です",
    )
    async def register(
        interaction: discord.Interaction,
        name: str,
        student_number: str,
        grade: GradeOption,
        email: str,
    ) -> None:
        # [F2] 個人情報を含むため、応答はすべて実行者にだけ見える (ephemeral) メッセージにする
        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = str(interaction.user.id)

        # 管理者 (Administrator ロールを持つメンバー) だけが実行できる
        if not await bot.controllers.role.is_admin(user_id):
            await interaction.followup.send("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        try:
            student = bot.controllers.student.register_student(name, student_number, grade, email)
        except StudentRegistrationError as error:
            await interaction.followup.send(f"登録できませんでした: {error}", ephemeral=True)
            return

        logger.info("User %s registered student %s", user_id, student.uuid)
        await bot.controllers.audit.student_registered(user_id, student)
        await interaction.followup.send(
            f"{student.name} さんを登録しました。\n"
            f"学籍番号: {student.student_number} / 学年: {student.grade.value} / メール: {student.email}",
            ephemeral=True,
        )
