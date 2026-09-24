"""
DM での認証手続きの途中経過を保持するデータクラス定義
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from .grade import Grade


class AuthStep(Enum):
    """
    認証手続きの段階 (次にユーザーから何を受け取るか)

    NAME → STUDENT_NUMBER → GRADE → EMAIL → CODE の順に進みます。
    """

    NAME = auto()
    """氏名の入力待ち"""
    STUDENT_NUMBER = auto()
    """学籍番号の入力待ち"""
    GRADE = auto()
    """学年の入力待ち"""
    EMAIL = auto()
    """メールアドレスの入力待ち"""
    CODE = auto()
    """メールで送った認証コードの入力待ち"""


@dataclass
class AuthSession:
    """
    1 人のユーザーの認証手続きの途中経過

    Bot を再起動すると失われます (ユーザーは最初からやり直します)。

    Attributes:
        step (AuthStep): 現在の段階
        name (str | None): 入力された氏名
        student_number (str | None): 入力された学籍番号
        grade (Grade | None): 入力された学年
        email (str | None): 入力されたメールアドレス
        student_uuid (str | None): 入力内容と一致した学生情報の uuid
        code (str | None): メールで送った認証コード
        code_expires_at (datetime | None): 認証コードの有効期限
        failed_code_attempts (int): 認証コードを間違えた回数
    """

    step: AuthStep = AuthStep.NAME
    name: str | None = None
    student_number: str | None = None
    grade: Grade | None = None
    email: str | None = None
    student_uuid: str | None = None
    code: str | None = None
    code_expires_at: datetime | None = None
    failed_code_attempts: int = 0
