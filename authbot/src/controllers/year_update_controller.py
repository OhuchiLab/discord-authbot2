"""
現役メンバーの年度更新を行うコントローラー

流れ:

    1. create_plan()        学生情報から更新候補を作る (この時点では何も変更しない)
    2. change_next_grade()  管理者が留年・卒業・進学などの例外に合わせて更新先を変える
    3. commit()             学生情報を更新し、その内容を Discord の学年ロールに反映する

学生情報が正で、Discord のロールはその結果を反映したものです (学生情報 → ロール の一方向)。
"""

import dataclasses
import logging
from collections.abc import Callable
from datetime import date

from database import DatabaseController
from external import MemberNotFoundError
from several_types import Grade, StudentInfo, YearUpdateCandidate, YearUpdatePlan, YearUpdateResult

from .role_controller import RoleController

logger = logging.getLogger(__name__)

DEFAULT_NEXT_GRADES: dict[Grade, Grade] = {
    Grade.B4: Grade.M1,
    Grade.M1: Grade.M2,
    Grade.M2: Grade.OBOG,
    Grade.D1: Grade.D2,
    Grade.D2: Grade.D3,
    Grade.D3: Grade.OBOG,
}
"""通常の進級規則 (今の学年 → 翌年度の学年)。ここに無い学年 (OB/OG・教員) は年度更新の対象外"""

SELECTABLE_NEXT_GRADES: list[Grade] = [Grade.B4, Grade.M1, Grade.M2, Grade.D1, Grade.D2, Grade.D3, Grade.OBOG]
"""管理者が確認画面で選べる更新先"""

FISCAL_YEAR_START_MONTH = 4
"""年度が始まる月 (日本の年度: 4 月始まり)"""


class YearUpdateError(Exception):
    """
    年度更新ができないときに送出される例外

    メッセージはそのまま Discord 上で管理者に表示されます。
    """


class YearUpdateController:
    """
    現役メンバーの年度更新に関する業務ルールをまとめたクラス
    """

    def __init__(
        self,
        database: DatabaseController,
        role_controller: RoleController,
        today: Callable[[], date] = date.today,
    ):
        """
        コンストラクタ

        Args:
            database (DatabaseController): 学生情報データベース
            role_controller (RoleController): 学年ロールの同期に使う
            today (Callable[[], date]): 今日の日付を返す関数 (テストで差し替えるため)
        """
        self._database = database
        self._roles = role_controller
        self._today = today

    def default_fiscal_year(self) -> int:
        """
        年度を省略したときの対象年度 (= 今日が属する年度の、次の年度) を返す

        例: 2026年9月 → 2026年度の途中なので 2027、2027年4月1日 → 2027年度の初日なので 2028
        """
        today = self._today()
        current_fiscal_year = today.year if today.month >= FISCAL_YEAR_START_MONTH else today.year - 1
        return current_fiscal_year + 1

    def create_plan(self, fiscal_year: int | None = None) -> YearUpdatePlan:
        """
        学生情報から、翌年度の更新候補を作る。学生情報・ロールは変更しない

        Args:
            fiscal_year (int | None): 対象年度。None なら `default_fiscal_year()`

        Returns:
            YearUpdatePlan: 現役学生 (`DEFAULT_NEXT_GRADES` にある学年の学生) の更新候補

        Raises:
            YearUpdateError: その年度が実行済み、または対象の学生がいない場合
        """
        if fiscal_year is None:
            fiscal_year = self.default_fiscal_year()
        self._check_not_completed(fiscal_year)

        candidates = [
            YearUpdateCandidate(
                student_uuid=student.uuid,
                name=student.name,
                discord_id=student.discord_id,
                current_grade=student.grade,
                default_next_grade=DEFAULT_NEXT_GRADES[student.grade],
                next_grade=DEFAULT_NEXT_GRADES[student.grade],
            )
            for student in self._active_students()
        ]
        if not candidates:
            raise YearUpdateError("年度更新の対象となる現役メンバーがいません。")
        return YearUpdatePlan(fiscal_year=fiscal_year, candidates=candidates)

    def change_next_grade(self, plan: YearUpdatePlan, student_uuid: str, next_grade: Grade) -> None:
        """
        1 人の学生の更新先を変更する (留年・卒業・進学など)

        Args:
            plan (YearUpdatePlan): 変更する計画
            student_uuid (str): 学生情報の uuid
            next_grade (Grade): 新しい更新先 (`SELECTABLE_NEXT_GRADES` のいずれか)

        Raises:
            YearUpdateError: 選べない学年を指定した場合
        """
        if next_grade not in SELECTABLE_NEXT_GRADES:
            raise YearUpdateError(f"{next_grade.value} は更新先に選べません。")
        plan.find(student_uuid).next_grade = next_grade

    async def commit(self, plan: YearUpdatePlan) -> YearUpdateResult:
        """
        年度更新を確定する

        1. 計画を作った後に、他の管理者の確定や学生情報の変更が無かったか確認する
        2. 学生情報を更新し、実行済みの年度を記録する (1 回の保存でまとめて行う)
        3. 認証済みの学生の学年ロールを、更新後の学生情報に合わせる

        Args:
            plan (YearUpdatePlan): 確定する計画

        Returns:
            YearUpdateResult: 更新した人数、ロールを同期した人数など

        Raises:
            YearUpdateError: 年度が実行済み、または計画を作った後に学生情報が変わった場合 (何も変更しない)
        """
        self._check_not_completed(plan.fiscal_year)
        self._check_plan_is_up_to_date(plan)

        updated_students = [
            dataclasses.replace(self._database.find_by_uuid(candidate.student_uuid), grade=candidate.next_grade)
            for candidate in plan.candidates
        ]
        self._database.commit_year_update(updated_students, plan.fiscal_year)
        logger.info("Committed year update for fiscal year %d (%d students)", plan.fiscal_year, len(updated_students))

        synced_count, not_in_server, problems = await self._sync_roles(updated_students)
        return YearUpdateResult(
            fiscal_year=plan.fiscal_year,
            updated_count=len(updated_students),
            synced_count=synced_count,
            not_in_server=not_in_server,
            problems=problems,
        )

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    def _active_students(self) -> list[StudentInfo]:
        """現役学生 (年度更新の対象) を返す"""
        return [student for student in self._database.get_all() if student.grade in DEFAULT_NEXT_GRADES]

    def _check_not_completed(self, fiscal_year: int) -> None:
        """その年度が実行済みなら YearUpdateError"""
        if fiscal_year in self._database.completed_fiscal_years():
            raise YearUpdateError(f"{fiscal_year}年度の現役更新は既に実行されています。")

    def _check_plan_is_up_to_date(self, plan: YearUpdatePlan) -> None:
        """計画を作った後に、現役学生の顔ぶれや学年が変わっていたら YearUpdateError"""
        planned = {candidate.student_uuid: candidate.current_grade for candidate in plan.candidates}
        current = {student.uuid: student.grade for student in self._active_students()}
        if planned != current:
            raise YearUpdateError(
                "更新候補を作った後に学生情報が変更されました。もう一度 /update_grades からやり直してください。"
            )

    async def _sync_roles(self, students: list[StudentInfo]) -> tuple[int, list[str], list[str]]:
        """
        認証済みの学生の学年ロールを学生情報に合わせる

        Returns:
            tuple: (同期した人数, サーバーにいない学生の氏名, うまくいかなかった処理の説明)
        """
        synced_count = 0
        not_in_server: list[str] = []
        problems: list[str] = []
        for student in students:
            if student.discord_id is None:
                continue
            try:
                student_problems = await self._roles.sync_grade_role(student.discord_id, student)
            except MemberNotFoundError:
                not_in_server.append(student.name)
                continue
            if student_problems:
                problems += [f"{student.name}: {problem}" for problem in student_problems]
            else:
                synced_count += 1
        return synced_count, not_in_server, problems
