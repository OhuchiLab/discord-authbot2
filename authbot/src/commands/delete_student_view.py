"""
/delete_student の確認画面 (削除する学生情報の表示と、削除・キャンセルのボタン)

画面の構成:

    [埋め込み] 学生情報の削除: 山田 太郎
               氏名: 山田 太郎
               学籍番号: AB123456
               …
               ⚠️ この操作は取り消せません。
    [ボタン]   削除する / キャンセル

処理の中身は `controllers.StudentDeleteController` が行い、この画面は表示と操作の受け付けだけを行います。
"""

from __future__ import annotations

import logging

import discord

from controllers import StudentDeleteController, StudentDeleteError
from several_types import StudentDeleteResult, StudentInfo

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 14 * 60
"""操作されないまま、この秒数が経つとキャンセル扱いにする (Discord の応答の有効期限 15 分より短くする)"""


def describe_result(result: StudentDeleteResult) -> str:
    """確定した結果を、管理者向けの文章にする"""
    lines = [f"{result.student.name} さんの学生情報を削除しました。"]
    if result.discord_synced:
        lines.append("Discord 上では未認証の状態に戻しました (Authorized・学年ロールを外し、Unauthorized を付けました)。")
    elif result.not_in_server:
        lines.append("サーバーにいないため、Discord のロールは変更していません。")
    lines += result.problems
    return "\n".join(lines)


class StudentDeleteView(discord.ui.View):
    """
    /delete_student の確認画面

    テストからも操作できるよう、各操作は `confirm()` / `cancel()` で受け付けます。
    """

    def __init__(
        self,
        controller: StudentDeleteController,
        student: StudentInfo,
        admin_id: int,
        original_interaction: discord.Interaction,
    ):
        """
        コンストラクタ

        Args:
            controller (StudentDeleteController): 削除の確定に使う
            student (StudentInfo): 削除する学生情報
            admin_id (int): /delete_student を実行した管理者の Discord ユーザー ID (この人だけが操作できる)
            original_interaction (discord.Interaction): /delete_student の実行 (時間切れのときに画面を書き換えるため)
        """
        super().__init__(timeout=TIMEOUT_SECONDS)
        self._controller = controller
        self._student = student
        self._admin_id = admin_id
        self._original_interaction = original_interaction

    def render(self) -> discord.Embed:
        """削除する学生情報と注意事項を表示する埋め込みを作る"""
        student = self._student
        lines = [
            f"氏名: {student.name}",
            f"学籍番号: {student.student_number}",
            f"学年: {student.grade.value}",
            f"メールアドレス: {student.email}",
            f"Discord: {f'<@{student.discord_id}>' if student.discord_id else 'なし (未認証)'}",
            "",
            "⚠️ この操作は取り消せません。",
        ]
        if student.discord_id:
            lines.append("この人の Discord アカウントは未認証の状態に戻ります (Authorized・学年ロールを外し、Unauthorized を付与)。")
        embed = discord.Embed(title=f"学生情報の削除: {student.name}", description="\n".join(lines))
        embed.set_footer(text="内容を確認して「削除する」を押してください。")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """/delete_student を実行した管理者だけが操作できる"""
        return interaction.user.id == self._admin_id

    @discord.ui.button(label="削除する", style=discord.ButtonStyle.danger)
    async def _confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.confirm(interaction)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def _cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cancel(interaction)

    async def confirm(self, interaction: discord.Interaction) -> None:
        """削除する: 学生情報を削除し、Discord 上で未認証の状態に戻す"""
        self.stop()
        await interaction.response.edit_message(content="削除しています…", embed=self.render(), view=None)
        try:
            result = await self._controller.commit(self._student)
        except StudentDeleteError as error:
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
            logger.warning("Failed to update the delete_student message after timeout")
