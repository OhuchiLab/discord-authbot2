"""
/update_grades コマンド: 年度の切り替えに合わせて、現役メンバーの学年を更新する (管理者のみ)

このコマンドは更新候補を表示するだけです。
学生情報とロールは、確認画面 (`update_grades_view.YearUpdateView`) で「確定する」を押したときに更新されます。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from controllers import YearUpdateError

from .update_grades_view import YearUpdateView

if TYPE_CHECKING:
    from bot import AuthBot


def setup_update_grades_command(bot: AuthBot) -> None:
    """
    /update_grades コマンドを Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """

    @bot.tree.command(
        name="update_grades",
        description="年度の切り替えに合わせて、現役メンバーの学年を更新します (管理者のみ)",
        guild=bot.guild_object,
    )
    @app_commands.describe(fiscal_year="対象の年度 (例: 2027)。省略すると次の年度")
    async def update_grades(
        interaction: discord.Interaction,
        fiscal_year: app_commands.Range[int, 2000, 2100] | None = None,
    ) -> None:
        # [F9] 個人情報を含むため、応答はすべて実行者にだけ見える (ephemeral) メッセージにする
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 管理者 (Administrator ロールを持つメンバー) だけが実行できる
        if not await bot.controllers.role.is_admin(str(interaction.user.id)):
            await interaction.followup.send("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        try:
            plan = bot.controllers.year_update.create_plan(fiscal_year)
        except YearUpdateError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        view = YearUpdateView(bot.controllers.year_update, plan, interaction.user.id, interaction)
        await interaction.followup.send(embed=view.render(), view=view, ephemeral=True)
