"""
学生情報の登録・検索・変更・Discord アカウントとの紐付けを行うコントローラー
"""

import dataclasses
import uuid

from database import DatabaseController
from several_types import Grade, StudentEdit, StudentInfo
from utils import (
    is_valid_email,
    is_valid_student_number,
    normalize_email,
    normalize_input,
    normalize_name,
    normalize_student_number,
)


class StudentRegistrationError(Exception):
    """
    学生情報の登録に失敗したときに送出される例外

    メッセージはそのまま Discord 上で管理者に表示されます。
    """


class StudentEditError(Exception):
    """
    学生情報の変更に失敗したときに送出される例外

    メッセージはそのまま Discord 上で管理者に表示されます。
    """


class StudentLinkError(Exception):
    """
    学生情報と Discord アカウントの紐付けに失敗したときに送出される例外

    メッセージはそのまま Discord 上でユーザーに表示されます。
    """


class StudentController:
    """
    学生情報に関する業務ルール (入力チェック・重複チェック・照合) を担当するクラス

    データの保存そのものは `database.DatabaseController` に任せます。
    """

    def __init__(self, database: DatabaseController, allowed_email_domain: str):
        """
        コンストラクタ

        Args:
            database (DatabaseController): 学生情報データベース
            allowed_email_domain (str): 登録を許可するメールアドレスのドメイン
        """
        self._database = database
        self._allowed_email_domain = allowed_email_domain

    def register_student(self, name: str, student_number: str, grade: Grade, email: str) -> StudentInfo:
        """
        新しい学生情報を登録する (管理者の /register コマンドから呼ばれる)

        Args:
            name (str): 氏名
            student_number (str): 学籍番号
            grade (Grade): 学年
            email (str): メールアドレス

        Returns:
            StudentInfo: 登録した学生情報

        Raises:
            StudentRegistrationError: 入力値の形式が不正、または学籍番号・メールアドレスが登録済みの場合
        """
        problem = self._find_format_problem(name, student_number, email) or self._find_duplicate_problem(
            student_number, email
        )
        if problem:
            raise StudentRegistrationError(problem)

        name = normalize_input(name)
        student_number = normalize_student_number(student_number)
        email = normalize_email(email)
        student = StudentInfo(
            uuid=str(uuid.uuid4()),
            name=name,
            student_number=student_number,
            email=email,
            grade=grade,
        )
        self._database.add(student)
        return student

    def find_matching_student(
        self, name: str, student_number: str, grade: Grade, email: str
    ) -> StudentInfo | None:
        """
        氏名・学籍番号・学年・メールアドレスのすべてが一致する学生情報を探す

        氏名の空白、学籍番号とメールアドレスの大文字・小文字は区別しません。

        Returns:
            StudentInfo | None: 一致した学生情報。見つからなければ None
        """
        for student in self._database.get_all():
            if (
                normalize_name(student.name) == normalize_name(name)
                and normalize_student_number(student.student_number) == normalize_student_number(student_number)
                and student.grade == grade
                and normalize_email(student.email) == normalize_email(email)
            ):
                return student
        return None

    def find_by_uuid(self, student_uuid: str) -> StudentInfo | None:
        """
        uuid が一致する学生情報を返す。見つからなければ None
        """
        return self._database.find_by_uuid(student_uuid)

    def find_by_student_number(self, student_number: str) -> StudentInfo | None:
        """
        学籍番号が一致する学生情報を返す (大文字・小文字、全角・半角は区別しない)。見つからなければ None
        """
        target = normalize_student_number(student_number)
        return next(
            (s for s in self._database.get_all() if normalize_student_number(s.student_number) == target), None
        )

    def find_by_discord_id(self, discord_id: str) -> StudentInfo | None:
        """
        Discord ID に紐付いた (= 認証済みの) 学生情報を返す。見つからなければ None
        """
        return self._database.find_by_discord_id(discord_id)

    def link_discord_id(self, student_uuid: str, discord_id: str) -> StudentInfo:
        """
        学生情報に Discord ID を紐付けて保存する (= 認証済みにする)

        Args:
            student_uuid (str): 紐付ける学生情報の uuid
            discord_id (str): Discord ユーザー ID

        Returns:
            StudentInfo: 紐付け後の学生情報

        Raises:
            StudentLinkError: 学生情報が存在しない、または別のアカウントと紐付け済みの場合
        """
        student = self._database.find_by_uuid(student_uuid)
        if student is None:
            raise StudentLinkError("学生情報が見つかりませんでした。管理者に連絡してください。")
        if student.discord_id not in (None, discord_id):
            raise StudentLinkError(
                "この学生情報はすでに別の Discord アカウントで認証されています。管理者に連絡してください。"
            )
        already_linked = self._database.find_by_discord_id(discord_id)
        if already_linked is not None and already_linked.uuid != student_uuid:
            raise StudentLinkError(
                "この Discord アカウントはすでに別の学生情報で認証されています。管理者に連絡してください。"
            )

        linked_student = dataclasses.replace(student, discord_id=discord_id)
        self._database.update(linked_student)
        return linked_student

    def prepare_edit(
        self,
        student: StudentInfo,
        new_name: str | None = None,
        new_student_number: str | None = None,
        new_grade: Grade | None = None,
        new_email: str | None = None,
        unlink_discord: bool = False,
    ) -> StudentEdit:
        """
        学生情報の変更内容 (変更前と変更後) を作る。保存はしない

        None の項目は変更しません。値の形式と、他の学生との重複は /register と同じ規則で確認します。

        Args:
            student (StudentInfo): 変更する学生情報
            new_name (str | None): 新しい氏名
            new_student_number (str | None): 新しい学籍番号
            new_grade (Grade | None): 新しい学年
            new_email (str | None): 新しいメールアドレス
            unlink_discord (bool): True なら Discord アカウントとの紐付けを解除する

        Returns:
            StudentEdit: 変更内容

        Raises:
            StudentEditError: 変更する項目が無い、値の形式が不正、他の学生と重複する、
                または紐付いていないのに紐付けを解除しようとした場合
        """
        if unlink_discord and student.discord_id is None:
            raise StudentEditError("この学生情報は Discord アカウントと紐付いていません。")

        name = normalize_input(new_name) if new_name is not None else student.name
        student_number = (
            normalize_student_number(new_student_number) if new_student_number is not None else student.student_number
        )
        email = normalize_email(new_email) if new_email is not None else student.email
        problem = self._find_format_problem(name, student_number, email) or self._find_duplicate_problem(
            student_number, email, exclude_uuid=student.uuid
        )
        if problem:
            raise StudentEditError(problem)

        edit = StudentEdit(
            before=student,
            after=dataclasses.replace(
                student,
                name=name,
                student_number=student_number,
                grade=new_grade if new_grade is not None else student.grade,
                email=email,
                discord_id=None if unlink_discord else student.discord_id,
            ),
        )
        if not edit.changed_fields():
            raise StudentEditError("変更する項目を指定してください。")
        return edit

    def apply_edit(self, edit: StudentEdit) -> StudentInfo:
        """
        変更内容を保存する

        変更内容を作った後に、他の管理者などが同じ学生情報を変更していた場合や、
        他の学生と重複するようになっていた場合は保存しません。

        Args:
            edit (StudentEdit): `prepare_edit()` で作った変更内容

        Returns:
            StudentInfo: 保存した学生情報

        Raises:
            StudentEditError: 学生情報が変更されていた、または重複が生じていた場合 (何も変更しない)
        """
        if self._database.find_by_uuid(edit.before.uuid) != edit.before:
            raise StudentEditError(
                "確認している間に、この学生情報が変更されました。もう一度 /edit_student からやり直してください。"
            )
        problem = self._find_duplicate_problem(edit.after.student_number, edit.after.email, exclude_uuid=edit.after.uuid)
        if problem:
            raise StudentEditError(problem)
        self._database.update(edit.after)
        return edit.after

    # ------------------------------------------------------------------
    # 内部処理 (登録と変更で共通の確認)
    # ------------------------------------------------------------------

    def _find_format_problem(self, name: str, student_number: str, email: str) -> str | None:
        """値の形式が不正なら、その説明を返す。問題なければ None"""
        if not normalize_input(name):
            return "氏名が空です。"
        if not is_valid_student_number(student_number):
            return "学籍番号は英数字 8 文字で入力してください。"
        if not is_valid_email(email, self._allowed_email_domain):
            return f"メールアドレスは @{self._allowed_email_domain} のアドレスを入力してください。"
        return None

    def _find_duplicate_problem(self, student_number: str, email: str, exclude_uuid: str | None = None) -> str | None:
        """学籍番号・メールアドレスが他の学生と重複していれば、その説明を返す。問題なければ None"""
        student_number = normalize_student_number(student_number)
        email = normalize_email(email)
        for registered in self._database.get_all():
            if registered.uuid == exclude_uuid:
                continue
            if normalize_student_number(registered.student_number) == student_number:
                return f"学籍番号 {student_number} はすでに登録されています。"
            if normalize_email(registered.email) == email:
                return f"メールアドレス {email} はすでに登録されています。"
        return None
