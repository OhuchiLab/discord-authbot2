"""
/update_grades の確認画面 (更新候補の一覧と、変更・確定・キャンセルの操作部品)

画面の構成:

    [埋め込み] 2027年度 現役メンバー更新
               @A 山田 太郎   B3 → B4
               @B 鈴木 花子   B4 → B4 (留年) ✏️
    [セレクト] 更新先を変更する学生を選ぶ
    [セレクト] 選んだ学生の更新先 (学生を選ぶと表示)
    [ボタン]   ◀ 前へ / 次へ ▶ (25 人を超えるとき)
    [ボタン]   確定する / キャンセル

処理の中身は `controllers.YearUpdateController` が行い、この画面は表示と操作の受け付けだけを行います。
"""

from __future__ import annotations

import logging

import discord

from controllers import YearUpdateController, YearUpdateError
from controllers.year_update_controller import SELECTABLE_NEXT_GRADES
from several_types import Grade, YearUpdateCandidate, YearUpdatePlan, YearUpdateResult

logger = logging.getLogger(__name__)

PAGE_SIZE = 25
"""1 ページに表示する学生の数 (Discord のセレクトメニューの選択肢は 25 個まで)"""

TIMEOUT_SECONDS = 14 * 60
"""操作されないまま、この秒数が経つとキャンセル扱いにする (Discord の応答の有効期限 15 分より短くする)"""


def describe_transition(candidate: YearUpdateCandidate) -> str:
    """
    更新内容を「B4 → M1」の形で表す。留年・卒業と、管理者が変更したものには目印を付ける
    """
    text = f"{candidate.current_grade.value} → {candidate.next_grade.value}"
    if candidate.next_grade == candidate.current_grade:
        text += " (留年)"
    elif candidate.next_grade == Grade.OBOG:
        text += " (卒業・修了)"
    if candidate.is_changed:
        text += " ✏️"
    return text


def describe_student(candidate: YearUpdateCandidate) -> str:
    """学生を「@メンション 氏名」の形で表す。未認証なら「氏名 (未認証)」"""
    if candidate.discord_id is None:
        return f"{candidate.name} (未認証)"
    return f"<@{candidate.discord_id}> {candidate.name}"


def describe_result(result: YearUpdateResult) -> str:
    """確定した結果を、管理者向けの文章にする"""
    lines = [
        f"{result.fiscal_year}年度の現役更新を実行し、{result.updated_count} 人の学生情報を更新しました。",
        f"Discord の学年ロールを {result.synced_count} 人分更新しました。",
    ]
    if result.not_in_server:
        lines.append(f"サーバーにいないため、ロールを更新できなかった人: {', '.join(result.not_in_server)}")
    lines += result.problems
    return "\n".join(lines)


class YearUpdateView(discord.ui.View):
    """
    /update_grades の確認画面

    テストからも操作できるよう、各操作は次のメソッドで受け付けます。
    `select_student()` / `select_next_grade()` / `show_page()` / `confirm()` / `cancel()`
    """

    def __init__(
        self,
        controller: YearUpdateController,
        plan: YearUpdatePlan,
        admin_id: int,
        original_interaction: discord.Interaction,
    ):
        """
        コンストラクタ

        Args:
            controller (YearUpdateController): 更新先の変更・確定に使う
            plan (YearUpdatePlan): 表示する更新候補
            admin_id (int): /update_grades を実行した管理者の Discord ユーザー ID (この人だけが操作できる)
            original_interaction (discord.Interaction): /update_grades の実行 (時間切れのときに画面を書き換えるため)
        """
        super().__init__(timeout=TIMEOUT_SECONDS)
        self._controller = controller
        self._plan = plan
        self._admin_id = admin_id
        self._original_interaction = original_interaction
        self._page = 0
        self._selected_uuid: str | None = None
        self._rebuild_items()

    # ------------------------------------------------------------------
    # 表示
    # ------------------------------------------------------------------

    def render(self) -> discord.Embed:
        """今のページの更新候補を一覧にした埋め込み表示を作る"""
        lines = [
            f"{describe_student(candidate)}\n　{describe_transition(candidate)}" for candidate in self._page_candidates()
        ]
        embed = discord.Embed(
            title=f"{self._plan.fiscal_year}年度 現役メンバー更新",
            description="\n".join(lines),
        )
        footer = "内容を確認し、例外 (留年・卒業・進学など) があれば下のメニューで変更してから「確定する」を押してください。"
        if self._page_count() > 1:
            footer = f"{self._page + 1} / {self._page_count()} ページ　" + footer
        embed.set_footer(text=footer)
        return embed

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """/update_grades を実行した管理者だけが操作できる"""
        return interaction.user.id == self._admin_id

    async def select_student(self, interaction: discord.Interaction, student_uuid: str) -> None:
        """更新先を変更する学生を選ぶ"""
        self._selected_uuid = student_uuid
        await self._refresh(interaction)

    async def select_next_grade(self, interaction: discord.Interaction, next_grade: Grade) -> None:
        """選んだ学生の更新先を変更する"""
        if self._selected_uuid is not None:
            self._controller.change_next_grade(self._plan, self._selected_uuid, next_grade)
        await self._refresh(interaction)

    async def show_page(self, interaction: discord.Interaction, page: int) -> None:
        """別のページを表示する"""
        self._page = max(0, min(page, self._page_count() - 1))
        self._selected_uuid = None
        await self._refresh(interaction)

    async def confirm(self, interaction: discord.Interaction) -> None:
        """確定する: 学生情報を更新し、学年ロールに反映する"""
        self.stop()
        await interaction.response.edit_message(content="更新しています…", embed=self.render(), view=None)
        try:
            result = await self._controller.commit(self._plan)
        except YearUpdateError as error:
            await interaction.edit_original_response(content=str(error), embed=None, view=None)
            return
        await interaction.edit_original_response(content=describe_result(result), embed=None, view=None)

    async def cancel(self, interaction: discord.Interaction) -> None:
        """キャンセルする: 何も変更しない"""
        self.stop()
        await interaction.response.edit_message(
            content="キャンセルしました。学生情報・ロールは変更していません。", embed=None, view=None
        )

    async def on_timeout(self) -> None:
        """時間切れ: キャンセルと同じく何も変更しない"""
        try:
            await self._original_interaction.edit_original_response(
                content="操作されないまま時間が経ったため、キャンセルしました。学生情報・ロールは変更していません。",
                embed=None,
                view=None,
            )
        except discord.HTTPException:
            logger.warning("Failed to update the year update message after timeout")

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    def _page_count(self) -> int:
        return (len(self._plan.candidates) + PAGE_SIZE - 1) // PAGE_SIZE

    def _page_candidates(self) -> list[YearUpdateCandidate]:
        start = self._page * PAGE_SIZE
        return self._plan.candidates[start : start + PAGE_SIZE]

    async def _refresh(self, interaction: discord.Interaction) -> None:
        """操作部品を作り直し、画面を書き換える"""
        self._rebuild_items()
        await interaction.response.edit_message(embed=self.render(), view=self)

    def _rebuild_items(self) -> None:
        """今の状態 (ページ・選んでいる学生) に合わせて、操作部品を並べ直す"""
        self.clear_items()
        self.add_item(_StudentSelect(self, self._page_candidates(), self._selected_uuid))
        if self._selected_uuid is not None:
            self.add_item(_NextGradeSelect(self, self._plan.find(self._selected_uuid)))
        if self._page_count() > 1:
            self.add_item(_PageButton(self, "◀ 前へ", self._page - 1, disabled=self._page == 0))
            self.add_item(_PageButton(self, "次へ ▶", self._page + 1, disabled=self._page >= self._page_count() - 1))
        self.add_item(_ConfirmButton(self))
        self.add_item(_CancelButton(self))


# ----------------------------------------------------------------------
# 操作部品 (受け取った操作を YearUpdateView のメソッドに渡すだけ)
# ----------------------------------------------------------------------


class _StudentSelect(discord.ui.Select):
    def __init__(self, view: YearUpdateView, candidates: list[YearUpdateCandidate], selected_uuid: str | None):
        options = [
            discord.SelectOption(
                label=candidate.name[:100],
                description=describe_transition(candidate),
                value=candidate.student_uuid,
                default=candidate.student_uuid == selected_uuid,
            )
            for candidate in candidates
        ]
        super().__init__(placeholder="更新先を変更する学生を選ぶ", options=options, row=0)
        self._year_update_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._year_update_view.select_student(interaction, self.values[0])


class _NextGradeSelect(discord.ui.Select):
    def __init__(self, view: YearUpdateView, candidate: YearUpdateCandidate):
        options = [
            discord.SelectOption(
                label=f"{candidate.current_grade.value} → {grade.value}",
                description="通常の進級" if grade == candidate.default_next_grade else None,
                value=grade.value,
                default=grade == candidate.next_grade,
            )
            for grade in SELECTABLE_NEXT_GRADES
        ]
        super().__init__(placeholder=f"{candidate.name} さんの更新先", options=options, row=1)
        self._year_update_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._year_update_view.select_next_grade(interaction, Grade(self.values[0]))


class _PageButton(discord.ui.Button):
    def __init__(self, view: YearUpdateView, label: str, page: int, disabled: bool):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=disabled, row=2)
        self._year_update_view = view
        self._target_page = page

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._year_update_view.show_page(interaction, self._target_page)


class _ConfirmButton(discord.ui.Button):
    def __init__(self, view: YearUpdateView):
        super().__init__(label="確定する", style=discord.ButtonStyle.danger, row=3)
        self._year_update_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._year_update_view.confirm(interaction)


class _CancelButton(discord.ui.Button):
    def __init__(self, view: YearUpdateView):
        super().__init__(label="キャンセル", style=discord.ButtonStyle.secondary, row=3)
        self._year_update_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._year_update_view.cancel(interaction)
