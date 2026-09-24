"""
/edit_student の確認画面 (変更前後の表示と、確定・キャンセルのボタン)

画面の構成:

    [埋め込み] 学生情報の変更: 山田 太郎
               学年: B4 → M1
               氏名: 山田 太郎 → 山田 次郎
    [ボタン]   確定する / キャンセル

処理の中身は `controllers.StudentEditController` が行い、この画面は表示と操作の受け付けだけを行います。
"""

from __future__ import annotations

import logging

import discord

from controllers import StudentEditController, StudentEditError
from several_types import FIELD_LABELS, StudentEdit, StudentEditResult, StudentInfo

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 14 * 60
"""操作されないまま、この秒数が経つとキャンセル扱いにする (Discord の応答の有効期限 15 分より短くする)"""


def describe_value(student: StudentInfo, field: str) -> str:
    """学生情報の 1 項目を、画面に表示する文字列にする"""
    if field == "grade":
        return student.grade.value
    if field == "discord_id":
        return f"<@{student.discord_id}>" if student.discord_id else "なし (未認証)"
    return str(getattr(student, field))


def describe_result(result: StudentEditResult) -> str:
    """確定した結果を、管理者向けの文章にする"""
    lines = [f"{result.student.name} さんの学生情報を変更しました。"]
    if result.discord_synced:
        lines.append("Discord のニックネーム・ロールにも反映しました。")
    elif result.not_in_server:
        lines.append("サーバーにいないため、Discord のニックネーム・ロールには反映していません。")
    elif result.student.discord_id is None:
        lines.append("未認証の学生のため、Discord は変更していません。")
    lines += result.problems
    return "\n".join(lines)


class StudentEditView(discord.ui.View):
    """
    /edit_student の確認画面

    テストからも操作できるよう、各操作は `confirm()` / `cancel()` で受け付けます。
    """

    def __init__(
        self,
        controller: StudentEditController,
        edit: StudentEdit,
        admin_id: int,
        original_interaction: discord.Interaction,
    ):
        """
        コンストラクタ

        Args:
            controller (StudentEditController): 変更の確定に使う
            edit (StudentEdit): 表示する変更内容
            admin_id (int): /edit_student を実行した管理者の Discord ユーザー ID (この人だけが操作できる)
            original_interaction (discord.Interaction): /edit_student の実行 (時間切れのときに画面を書き換えるため)
        """
        super().__init__(timeout=TIMEOUT_SECONDS)
        self._controller = controller
        self._edit = edit
        self._admin_id = admin_id
        self._original_interaction = original_interaction

    def render(self) -> discord.Embed:
        """変更前後を一覧にした埋め込み表示を作る"""
        lines = [
            f"{label}: {describe_value(self._edit.before, field)} → {describe_value(self._edit.after, field)}"
            for field, label in FIELD_LABELS.items()
            if getattr(self._edit.before, field) != getattr(self._edit.after, field)
        ]
        embed = discord.Embed(title=f"学生情報の変更: {self._edit.before.name}", description="\n".join(lines))
        if self._edit.unlinks_discord:
            embed.add_field(
                name="紐付けの解除について",
                value="このアカウントは未認証に戻り (Authorized・学年ロールを外して Unauthorized を付与)、もう一度認証できるようになります。",
                inline=False,
            )
        embed.set_footer(text="内容を確認して「確定する」を押してください。")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """/edit_student を実行した管理者だけが操作できる"""
        return interaction.user.id == self._admin_id

    @discord.ui.button(label="確定する", style=discord.ButtonStyle.danger)
    async def _confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.confirm(interaction)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def _cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cancel(interaction)

    async def confirm(self, interaction: discord.Interaction) -> None:
        """確定する: 学生情報を保存し、Discord に反映する"""
        self.stop()
        await interaction.response.edit_message(content="変更しています…", embed=self.render(), view=None)
        try:
            result = await self._controller.commit(self._edit)
        except StudentEditError as error:
            await interaction.edit_original_response(content=str(error), embed=None, view=None)
            return
        await interaction.edit_original_response(content=describe_result(result), embed=None, view=None)

    async def cancel(self, interaction: discord.Interaction) -> None:
        """キャンセルする: 何も変更しない"""
        self.stop()
        await interaction.response.edit_message(
            content="キャンセルしました。学生情報・Discord は変更していません。", embed=None, view=None
        )

    async def on_timeout(self) -> None:
        """時間切れ: キャンセルと同じく何も変更しない"""
        try:
            await self._original_interaction.edit_original_response(
                content="操作されないまま時間が経ったため、キャンセルしました。学生情報・Discord は変更していません。",
                embed=None,
                view=None,
            )
        except discord.HTTPException:
            logger.warning("Failed to update the edit_student message after timeout")
