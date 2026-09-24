"""
学生情報の一括登録 (/import_students) で使うデータクラス定義
"""

from dataclasses import dataclass, field

from .grade import Grade


@dataclass(frozen=True)
class NewStudent:
    """
    これから登録する学生 1 人分の入力内容 (uuid や Discord ID はまだ無い)

    Attributes:
        name (str): 氏名
        student_number (str): 学籍番号
        grade (Grade): 学年
        email (str): メールアドレス
    """

    name: str
    student_number: str
    grade: Grade
    email: str


@dataclass(frozen=True)
class ImportRow:
    """
    CSV の 1 行分

    Attributes:
        line (int): CSV の行番号 (見出しが 1 行目)
        student (NewStudent): その行の入力内容
    """

    line: int
    student: NewStudent


@dataclass(frozen=True)
class StudentImportPlan:
    """
    CSV を読み取った結果 (登録する前の確認用)

    Attributes:
        rows (list[ImportRow]): 登録する学生 (学年を読み取れた行)
        errors (list[str]): 行ごとの問題 (例: "3 行目: 氏名が空です。")。1 つでもあれば登録しない
    """

    rows: list[ImportRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
