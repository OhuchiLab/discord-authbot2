"""
変更履歴をログ用チャンネル (例: authbot-logs) に投稿するコントローラー

管理者が複数いても「誰が・いつ・何を・どう変えたか」を後から確認できるようにします。
投稿の日時は Discord のメッセージに残ります。

投稿に失敗しても (チャンネルが無い・権限が無いなど)、Bot のログに警告を残すだけで、
操作そのものは止めません (ログのせいで管理作業ができなくなるのを避けるため)。

    ⚠️ ログには氏名・学籍番号が含まれるため、ログ用チャンネルは管理者と Bot だけが見られる設定にすること
"""

import logging

from external import DiscordGateway, DiscordOperationError
from several_types import (
    ExportedFile,
    StudentDeleteResult,
    StudentEdit,
    StudentEditResult,
    StudentInfo,
    YearUpdatePlan,
    YearUpdateResult,
)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 2000
"""Discord の 1 メッセージの最大文字数。これより長いログは分けて投稿する"""

INDENT = "　"
"""ログの 2 行目以降の字下げ (全角空白)"""


def describe_student(student: StudentInfo) -> str:
    """学生を「氏名 (学籍番号)」の形で表す"""
    return f"{student.name} ({student.student_number})"


def mention(user_id: str) -> str:
    """Discord のメンション (投稿時に通知は飛ばさない)"""
    return f"<@{user_id}>"


class AuditLogController:
    """
    操作ごとに、変更履歴の文章を作って投稿するクラス

    各メソッドは、操作が成功した後に呼びます (キャンセルした操作は記録しない)。
    """

    def __init__(self, discord_gateway: DiscordGateway, channel_name: str | None):
        """
        コンストラクタ

        Args:
            discord_gateway (DiscordGateway): チャンネルへの投稿に使う
            channel_name (str | None): 投稿先のチャンネル名。None なら何も投稿しない
        """
        self._discord = discord_gateway
        self._channel_name = channel_name

    # ------------------------------------------------------------------
    # 操作ごとの記録
    # ------------------------------------------------------------------

    async def bot_started(self) -> None:
        """Bot の起動"""
        await self._post(["🟢 Bot を起動しました。"])

    async def student_registered(self, actor_id: str, student: StudentInfo) -> None:
        """/register による登録"""
        await self._post(
            [
                f"📝 学生情報の登録: {mention(actor_id)} が {describe_student(student)} を登録しました "
                f"(学年: {student.grade.value})"
            ]
        )

    async def students_imported(self, actor_id: str, students: list[StudentInfo]) -> None:
        """/import_students による一括登録"""
        await self._post(
            [
                f"📝 学生情報の一括登録: {mention(actor_id)} が {len(students)} 人を登録しました",
                *[f"{INDENT}{describe_student(student)} {student.grade.value}" for student in students],
            ]
        )

    async def student_edited(self, actor_id: str, edit: StudentEdit, result: StudentEditResult) -> None:
        """/edit_student による変更"""
        await self._post(
            [
                f"✏️ 学生情報の変更: {mention(actor_id)} が {describe_student(edit.before)} を変更しました",
                *[f"{INDENT}{change}" for change in edit.describe_changes()],
                *[f"{INDENT}⚠️ {problem}" for problem in result.problems],
            ]
        )

    async def student_deleted(self, actor_id: str, result: StudentDeleteResult) -> None:
        """/delete_student による削除"""
        lines = [f"🗑️ 学生情報の削除: {mention(actor_id)} が {describe_student(result.student)} を削除しました"]
        if result.student.discord_id is not None:
            status = "未認証に戻しました" if result.discord_synced else "サーバーにいないためロールは変更していません"
            lines.append(f"{INDENT}Discord: {mention(result.student.discord_id)} ({status})")
        lines += [f"{INDENT}⚠️ {problem}" for problem in result.problems]
        await self._post(lines)

    async def grades_updated(self, actor_id: str, plan: YearUpdatePlan, result: YearUpdateResult) -> None:
        """/update_grades による年度更新 (管理者が既定の更新先から変えたものには ✏️ を付ける)"""
        lines = [f"🎓 {plan.fiscal_year}年度の現役更新: {mention(actor_id)} が {result.updated_count} 人の学年を更新しました"]
        for candidate in plan.candidates:
            line = f"{INDENT}{candidate.name} ({candidate.student_number}): {candidate.transition_text()}"
            lines.append(line + (" ✏️" if candidate.is_changed else ""))
        lines += [f"{INDENT}⚠️ {problem}" for problem in result.problems]
        await self._post(lines)

    async def students_exported(self, actor_id: str, exported: ExportedFile, format_name: str) -> None:
        """/export_students による書き出し (個人情報を持ち出す操作)"""
        await self._post(
            [
                f"📤 学生情報の書き出し: {mention(actor_id)} が {exported.student_count} 人分を "
                f"{format_name} で書き出しました ({exported.filename})"
            ]
        )

    async def member_authenticated(self, student: StudentInfo) -> None:
        """メンバーの認証完了 (student.discord_id が認証したアカウント)"""
        await self._post(
            [
                f"✅ 認証: {mention(student.discord_id)} が {describe_student(student)} として認証されました "
                f"(学年: {student.grade.value})"
            ]
        )

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    async def _post(self, lines: list[str]) -> None:
        """
        ログを投稿する。長ければ行の区切りで分けて投稿する。失敗しても例外は出さない
        """
        if self._channel_name is None:
            return
        for message in self._split(lines):
            try:
                await self._discord.send_channel_message(self._channel_name, message)
            except DiscordOperationError as error:
                logger.warning("Failed to post audit log to #%s: %s", self._channel_name, error)
                return

    @staticmethod
    def _split(lines: list[str]) -> list[str]:
        """行を、1 メッセージが MAX_MESSAGE_LENGTH 文字以内になるようにまとめる"""
        messages: list[str] = []
        current = ""
        for line in lines:
            line = line[:MAX_MESSAGE_LENGTH]
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > MAX_MESSAGE_LENGTH:
                messages.append(current)
                candidate = line
            current = candidate
        if current:
            messages.append(current)
        return messages
