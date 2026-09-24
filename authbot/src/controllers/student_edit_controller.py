"""
管理者が特定の学生情報を手動で変更するコントローラー

流れ:

    1. prepare()  対象の学生を探し、変更内容 (変更前と変更後) を作る (この時点では何も変更しない)
    2. commit()   学生情報を保存し、認証済みの学生なら Discord のニックネーム・ロールに反映する

学生情報が正で、Discord のニックネーム・ロールはその結果を反映したものです (学生情報 → Discord の一方向)。
"""

import logging

from external import MemberNotFoundError
from several_types import Grade, StudentEdit, StudentEditResult, StudentInfo

from .role_controller import RoleController
from .student_controller import StudentController, StudentEditError

logger = logging.getLogger(__name__)


class StudentEditController:
    """
    学生情報の手動変更 (/edit_student) の流れをまとめたクラス
    """

    def __init__(self, student_controller: StudentController, role_controller: RoleController):
        """
        コンストラクタ

        Args:
            student_controller (StudentController): 学生情報の検索・変更に使う
            role_controller (RoleController): Discord のニックネーム・ロールの反映に使う
        """
        self._students = student_controller
        self._roles = role_controller

    def prepare(
        self,
        student_number: str | None = None,
        discord_id: str | None = None,
        new_name: str | None = None,
        new_student_number: str | None = None,
        new_grade: Grade | None = None,
        new_email: str | None = None,
        unlink_discord: bool = False,
    ) -> StudentEdit:
        """
        対象の学生を探し、変更内容を作る。学生情報・Discord は変更しない

        対象は、学籍番号 (`student_number`) か Discord ユーザー ID (`discord_id`) のどちらか一方で指定します。
        変更する項目の引数は `StudentController.prepare_edit()` と同じです。

        Returns:
            StudentEdit: 変更内容

        Raises:
            StudentEditError: 対象の指定が正しくない、見つからない、または変更内容が不正な場合
        """
        student = self._find_target(student_number, discord_id)
        return self._students.prepare_edit(
            student,
            new_name=new_name,
            new_student_number=new_student_number,
            new_grade=new_grade,
            new_email=new_email,
            unlink_discord=unlink_discord,
        )

    async def commit(self, edit: StudentEdit) -> StudentEditResult:
        """
        変更を確定する: 学生情報を保存し、Discord に反映する

        - 紐付けを解除する場合: 以前のアカウントを未認証の状態に戻す (Authorized・学年ロールを外し Unauthorized を付ける)
        - 認証済みで、氏名か学年が変わる場合: ニックネームと学年ロールを付け直す
        - それ以外 (未認証、メールアドレス・学籍番号だけの変更): Discord は操作しない

        Discord への反映に失敗しても、学生情報の変更は取り消しません (学生情報が正のため)。

        Args:
            edit (StudentEdit): `prepare()` で作った変更内容

        Returns:
            StudentEditResult: 変更後の学生情報と、Discord への反映の結果

        Raises:
            StudentEditError: 確認している間に学生情報が変更された、または重複が生じた場合 (何も変更しない)
        """
        student = self._students.apply_edit(edit)
        logger.info("Edited student %s (%s)", student.uuid, ", ".join(edit.changed_fields()))

        if edit.unlinks_discord:
            return await self._sync_discord(edit.before.discord_id, student, revoke=True)
        needs_sync = edit.before.name != student.name or edit.before.grade != student.grade
        if student.discord_id is not None and needs_sync:
            return await self._sync_discord(student.discord_id, student, revoke=False)
        return StudentEditResult(student=student, discord_synced=False, not_in_server=False, problems=[])

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    def _find_target(self, student_number: str | None, discord_id: str | None) -> StudentInfo:
        """学籍番号か Discord ユーザー ID のどちらか一方で、対象の学生情報を探す"""
        if (student_number is None) == (discord_id is None):
            raise StudentEditError("学籍番号 (student_number) か メンバー (member) のどちらか一方を指定してください。")
        if student_number is not None:
            student = self._students.find_by_student_number(student_number)
            if student is None:
                raise StudentEditError(f"学籍番号 {student_number.strip().upper()} の学生情報が見つかりません。")
            return student
        student = self._students.find_by_discord_id(discord_id)
        if student is None:
            raise StudentEditError("このメンバーに紐付いた学生情報が見つかりません。")
        return student

    async def _sync_discord(self, user_id: str, student: StudentInfo, revoke: bool) -> StudentEditResult:
        """Discord のニックネーム・ロールに反映する。サーバーにいなければ反映しない"""
        try:
            if revoke:
                problems = await self._roles.revoke_authorization(user_id)
            else:
                problems = await self._roles.mark_as_authorized(user_id, student)
        except MemberNotFoundError:
            return StudentEditResult(student=student, discord_synced=False, not_in_server=True, problems=[])
        return StudentEditResult(student=student, discord_synced=True, not_in_server=False, problems=problems)
