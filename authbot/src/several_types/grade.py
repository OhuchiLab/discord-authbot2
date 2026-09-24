"""
学年を表す列挙型の定義
"""

from enum import Enum


class Grade(Enum):
    """
    研究室メンバーの学年

    値 (value) は Discord 上の表示やデータベースへの保存に使う文字列です。
    """

    B4 = "B4"
    M1 = "M1"
    M2 = "M2"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    TEACHER = "TEACHER"
    OBOG = "OB/OG"

    @classmethod
    def parse(cls, text: str) -> "Grade | None":
        """
        ユーザーが入力した文字列を Grade に変換する

        大文字・小文字や前後の空白は区別しません。
        "OB/OG" は "OBOG" と入力しても受け付けます。

        Args:
            text (str): ユーザーが入力した文字列 (例: "m1", "OB/OG")

        Returns:
            Grade | None: 対応する学年。該当しない場合は None
        """
        normalized = text.strip().upper()
        for grade in cls:
            if normalized in (grade.value, grade.name):
                return grade
        return None

    @classmethod
    def choices_text(cls) -> str:
        """
        ユーザーに提示する学年の選択肢を、カンマ区切りの文字列で返す

        Returns:
            str: 例 "B4, M1, M2, D1, D2, D3, TEACHER, OB/OG"
        """
        return ", ".join(grade.value for grade in cls)
