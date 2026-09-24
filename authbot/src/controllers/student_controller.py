"""
学生情報の登録・検索・Discord アカウントとの紐付けを行うコントローラー
"""

import dataclasses
import uuid

from database import DatabaseController
from several_types import Grade, StudentInfo
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
        name = normalize_input(name)
        if not name:
            raise StudentRegistrationError("氏名が空です。")
        if not is_valid_student_number(student_number):
            raise StudentRegistrationError("学籍番号は英数字 8 文字で入力してください。")
        if not is_valid_email(email, self._allowed_email_domain):
            raise StudentRegistrationError(
                f"メールアドレスは @{self._allowed_email_domain} のアドレスを入力してください。"
            )

        student_number = normalize_student_number(student_number)
        email = normalize_email(email)
        for registered in self._database.get_all():
            if normalize_student_number(registered.student_number) == student_number:
                raise StudentRegistrationError(f"学籍番号 {student_number} はすでに登録されています。")
            if normalize_email(registered.email) == email:
                raise StudentRegistrationError(f"メールアドレス {email} はすでに登録されています。")

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
