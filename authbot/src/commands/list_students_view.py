"""
/list_students の表示 (学生情報の一覧と、ページ切り替えのボタン)

画面の構成:

    [埋め込み] 学生一覧
               全 30 人 (認証済み 25 人 / 未認証 5 人)
               山田 太郎 | AB123456 | M1 | yamada@shizuoka.ac.jp | @山田
               鈴木 花子 | CD123456 | B4 | suzuki@shizuoka.ac.jp | 未認証
    [ボタン]   ◀ 前へ / 次へ ▶ (PAGE_SIZE 人を超えるとき)
"""

from __future__ import annotations

import discord

from several_types import StudentInfo

PAGE_SIZE = 20
"""1 ページに表示する学生の数"""

TIMEOUT_SECONDS = 14 * 60
"""この秒数が経つと、ページ切り替えのボタンは使えなくなる (Discord の応答の有効期限 15 分より短くする)"""


def describe_student(student: StudentInfo) -> str:
    """学生情報を 1 行にする: 氏名 | 学籍番号 | 学年 | メールアドレス | Discord (未認証なら「未認証」)"""
    discord_text = f"<@{student.discord_id}>" if student.discord_id else "未認証"
    return " | ".join([student.name, student.student_number, student.grade.value, student.email, discord_text])


class StudentListView(discord.ui.View):
    """
    /list_students の一覧表示 (ページ切り替えのボタン付き)

    テストからも操作できるよう、ページの切り替えは `show_page()` で受け付けます。
    """

    def __init__(self, students: list[StudentInfo], filter_text: str, admin_id: int):
        """
        コンストラクタ

        Args:
            students (list[StudentInfo]): 表示する学生情報 (並び替え済み)
            filter_text (str): 絞り込み条件の説明 (例: "学年: B4")。絞り込みが無ければ空文字
            admin_id (int): /list_students を実行した管理者の Discord ユーザー ID (この人だけが操作できる)
        """
        super().__init__(timeout=TIMEOUT_SECONDS)
        self._students = students
        self._filter_text = filter_text
        self._admin_id = admin_id
        self._page = 0
        self._rebuild_items()

    @property
    def page_count(self) -> int:
        """ページ数"""
        return (len(self._students) + PAGE_SIZE - 1) // PAGE_SIZE

    def render(self) -> discord.Embed:
        """今のページの学生情報を一覧にした埋め込み表示を作る"""
        authenticated_count = sum(1 for student in self._students if student.discord_id is not None)
        summary = (
            f"全 {len(self._students)} 人 "
            f"(認証済み {authenticated_count} 人 / 未認証 {len(self._students) - authenticated_count} 人)"
        )
        start = self._page * PAGE_SIZE
        lines = [describe_student(student) for student in self._students[start : start + PAGE_SIZE]]
        embed = discord.Embed(title="学生一覧", description="\n".join([summary, "", *lines]))

        footer = ["氏名 | 学籍番号 | 学年 | メールアドレス | Discord"]
        if self._filter_text:
            footer.append(f"絞り込み: {self._filter_text}")
        if self.page_count > 1:
            footer.append(f"{self._page + 1} / {self.page_count} ページ")
        embed.set_footer(text="　".join(footer))
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """/list_students を実行した管理者だけが操作できる"""
        return interaction.user.id == self._admin_id

    async def show_page(self, interaction: discord.Interaction, page: int) -> None:
        """別のページを表示する"""
        self._page = max(0, min(page, self.page_count - 1))
        self._rebuild_items()
        await interaction.response.edit_message(embed=self.render(), view=self)

    def _rebuild_items(self) -> None:
        """今のページに合わせて、ボタンを並べ直す"""
        self.clear_items()
        self.add_item(_PageButton(self, "◀ 前へ", self._page - 1, disabled=self._page == 0))
        self.add_item(_PageButton(self, "次へ ▶", self._page + 1, disabled=self._page >= self.page_count - 1))


class _PageButton(discord.ui.Button):
    def __init__(self, view: StudentListView, label: str, page: int, disabled: bool):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=disabled)
        self._list_view = view
        self._target_page = page

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._list_view.show_page(interaction, self._target_page)
