"""
/import_students の確認画面 (登録する学生の一覧と、登録・キャンセルのボタン)

画面の構成:

    [埋め込み] 学生情報の一括登録 (2 人)
               山田 太郎 | AB123456 | B4 | yamada@shizuoka.ac.jp
               鈴木 花子 | CD123456 | M1 | suzuki@shizuoka.ac.jp
    [ボタン]   登録する / キャンセル

処理の中身は `controllers.ImportController` が行い、この画面は表示と操作の受け付けだけを行います。
"""

from __future__ import annotations

import logging

import discord

from controllers import ImportController, StudentImportError
from several_types import ImportRow, StudentImportPlan
from utils import normalize_email, normalize_input, normalize_student_number

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 14 * 60
"""操作されないまま、この秒数が経つとキャンセル扱いにする (Discord の応答の有効期限 15 分より短くする)"""

MAX_LINES = 30
"""確認画面に表示する学生の数 (それより多い分は「ほか N 人」とまとめる)"""

MAX_ERRORS = 20
"""エラーの一覧に表示する数"""

MAX_MESSAGE_LENGTH = 1900
"""エラーの一覧の最大文字数 (Discord のメッセージは 2000 文字まで。CSV に長い値があっても送れるようにする)"""


def describe_row(row: ImportRow) -> str:
    """登録する学生を 1 行にする: 氏名 | 学籍番号 | 学年 | メールアドレス (登録される形にそろえて表示)"""
    student = row.student
    return " | ".join(
        [
            normalize_input(student.name),
            normalize_student_number(student.student_number),
            student.grade.value,
            normalize_email(student.email),
        ]
    )


def describe_errors(errors: list[str]) -> str:
    """CSV の問題を、管理者向けの文章にする (多すぎる分は件数だけ示す)"""
    lines = ["CSV に問題があるため、何も登録していません。次の行を直して、もう一度実行してください。", ""]
    lines += errors[:MAX_ERRORS]
    if len(errors) > MAX_ERRORS:
        lines.append(f"…ほか {len(errors) - MAX_ERRORS} 件")
    text = "\n".join(lines)
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH] + "…"
    return text


class StudentImportView(discord.ui.View):
    """
    /import_students の確認画面

    テストからも操作できるよう、各操作は `confirm()` / `cancel()` で受け付けます。
    """

    def __init__(
        self,
        controller: ImportController,
        plan: StudentImportPlan,
        admin_id: int,
        original_interaction: discord.Interaction,
    ):
        """
        コンストラクタ

        Args:
            controller (ImportController): 登録の確定に使う
            plan (StudentImportPlan): 表示する登録内容 (問題が無いもの)
            admin_id (int): /import_students を実行した管理者の Discord ユーザー ID (この人だけが操作できる)
            original_interaction (discord.Interaction): /import_students の実行 (時間切れのときに画面を書き換えるため)
        """
        super().__init__(timeout=TIMEOUT_SECONDS)
        self._controller = controller
        self._plan = plan
        self._admin_id = admin_id
        self._original_interaction = original_interaction

    def render(self) -> discord.Embed:
        """登録する学生の一覧を表示する埋め込みを作る"""
        rows = self._plan.rows
        lines = [describe_row(row) for row in rows[:MAX_LINES]]
        if len(rows) > MAX_LINES:
            lines.append(f"…ほか {len(rows) - MAX_LINES} 人")
        embed = discord.Embed(title=f"学生情報の一括登録 ({len(rows)} 人)", description="\n".join(lines))
        embed.set_footer(text="氏名 | 学籍番号 | 学年 | メールアドレス　内容を確認して「登録する」を押してください。")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """/import_students を実行した管理者だけが操作できる"""
        return interaction.user.id == self._admin_id

    @discord.ui.button(label="登録する", style=discord.ButtonStyle.primary)
    async def _confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.confirm(interaction)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def _cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cancel(interaction)

    async def confirm(self, interaction: discord.Interaction) -> None:
        """登録する: 全員をまとめて登録する"""
        self.stop()
        await interaction.response.edit_message(content="登録しています…", embed=self.render(), view=None)
        try:
            registered = self._controller.commit(self._plan)
        except StudentImportError as error:
            await interaction.edit_original_response(content=str(error), embed=None, view=None)
            return
        await interaction.edit_original_response(
            content=f"{len(registered)} 人の学生情報を登録しました。", embed=None, view=None
        )

    async def cancel(self, interaction: discord.Interaction) -> None:
        """キャンセルする: 何も登録しない"""
        self.stop()
        await interaction.response.edit_message(
            content="キャンセルしました。学生情報は登録していません。", embed=None, view=None
        )

    async def on_timeout(self) -> None:
        """時間切れ: キャンセルと同じく何も登録しない"""
        try:
            await self._original_interaction.edit_original_response(
                content="操作されないまま時間が経ったため、キャンセルしました。学生情報は登録していません。",
                embed=None,
                view=None,
            )
        except discord.HTTPException:
            logger.warning("Failed to update the import_students message after timeout")
