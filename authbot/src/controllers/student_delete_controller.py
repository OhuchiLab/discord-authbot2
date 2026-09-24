"""
管理者が特定の学生情報を削除するコントローラー

流れ:

    1. prepare()  対象の学生を探す (この時点では何も変更しない)
    2. commit()   学生情報を削除し、認証済みの学生なら Discord 上で未認証の状態に戻す
"""

import logging

from external import MemberNotFoundError
from several_types import StudentDeleteResult, StudentInfo

from .role_controller import RoleController
from .student_controller import StudentController, StudentDeleteError, StudentNotFoundError

logger = logging.getLogger(__name__)


class StudentDeleteController:
    """
    学生情報の削除 (/delete_student) の流れをまとめたクラス
    """

    def __init__(self, student_controller: StudentController, role_controller: RoleController):
        """
        コンストラクタ

        Args:
            student_controller (StudentController): 学生情報の検索・削除に使う
            role_controller (RoleController): Discord 上で未認証の状態に戻すのに使う
        """
        self._students = student_controller
        self._roles = role_controller

    def prepare(self, student_number: str | None = None, discord_id: str | None = None) -> StudentInfo:
        """
        削除する学生を探す。学生情報・Discord は変更しない

        対象は、学籍番号 (`student_number`) か Discord ユーザー ID (`discord_id`) のどちらか一方で指定します。

        Returns:
            StudentInfo: 削除する学生情報

        Raises:
            StudentDeleteError: 対象の指定が正しくない、または見つからない場合
        """
        try:
            return self._students.find_target(student_number=student_number, discord_id=discord_id)
        except StudentNotFoundError as error:
            raise StudentDeleteError(str(error)) from error

    async def commit(self, student: StudentInfo) -> StudentDeleteResult:
        """
        削除を確定する: 学生情報を削除し、認証済みの学生なら Discord 上で未認証の状態に戻す

        未認証の状態に戻すとは、Authorized・学年ロールを外して Unauthorized を付けることです。
        Discord の変更に失敗しても、学生情報の削除は取り消しません (学生情報が正のため)。

        Args:
            student (StudentInfo): `prepare()` で見つけた学生情報

        Returns:
            StudentDeleteResult: 削除した学生情報と、Discord の変更の結果

        Raises:
            StudentDeleteError: 確認している間に学生情報が変更・削除された場合 (何も変更しない)
        """
        self._students.delete_student(student)
        logger.info("Deleted student %s", student.uuid)

        if student.discord_id is None:
            return StudentDeleteResult(student=student, discord_synced=False, not_in_server=False, problems=[])
        try:
            problems = await self._roles.revoke_authorization(student.discord_id)
        except MemberNotFoundError:
            return StudentDeleteResult(student=student, discord_synced=False, not_in_server=True, problems=[])
        return StudentDeleteResult(student=student, discord_synced=True, not_in_server=False, problems=problems)
