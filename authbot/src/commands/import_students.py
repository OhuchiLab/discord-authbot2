"""
/import_students コマンド: CSV ファイルから学生情報を一括登録する (管理者のみ)

このコマンドは登録する内容を表示するだけです。
学生情報は、確認画面 (`import_students_view.StudentImportView`) で「登録する」を押したときに登録されます。
CSV の形式は `controllers.import_controller` を参照してください。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from controllers import StudentImportError

from .import_students_view import StudentImportView, describe_errors

if TYPE_CHECKING:
    from bot import AuthBot

MAX_FILE_SIZE = 1024 * 1024
"""受け付ける CSV ファイルの大きさ (1MB)"""


def setup_import_students_command(bot: AuthBot) -> None:
    """
    /import_students コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(
        name="import_students",
        description="【管理者用】CSV から学生情報をまとめて登録します。列: 氏名, 学籍番号, 学年, メールアドレス",
        guild=bot.guild_object,
    )
    @app_commands.describe(
        file="CSV ファイル (1 行目は見出し。Excel の「CSV」形式でも可。/export_students の CSV と同じ形)",
    )
    async def import_students(interaction: discord.Interaction, file: discord.Attachment) -> None:
        # [F15] 個人情報を含むため、応答はすべて実行者にだけ見える (ephemeral) メッセージにする
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 管理者 (Administrator ロールを持つメンバー) だけが実行できる
        if not await bot.controllers.role.is_admin(str(interaction.user.id)):
            await interaction.followup.send("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        if not file.filename.lower().endswith(".csv"):
            await interaction.followup.send("CSV ファイル (拡張子 .csv) を添付してください。", ephemeral=True)
            return
        if file.size > MAX_FILE_SIZE:
            await interaction.followup.send("ファイルが大きすぎます (1MB まで)。CSV を分けてください。", ephemeral=True)
            return

        try:
            plan = bot.controllers.student_import.parse(await file.read())
        except StudentImportError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        if plan.errors:
            await interaction.followup.send(describe_errors(plan.errors), ephemeral=True)
            return

        view = StudentImportView(
            bot.controllers.student_import, bot.controllers.audit, plan, interaction.user.id, interaction
        )
        await interaction.followup.send(embed=view.render(), view=view, ephemeral=True)
