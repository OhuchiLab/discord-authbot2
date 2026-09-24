"""
学生情報を格納するデータクラス定義
"""

from dataclasses import dataclass

from .grade import Grade


@dataclass(frozen=True)
class StudentInfo:
    """
    学生情報を格納するデータクラス

    データベースに保存される 1 件分のレコードです。
    誤って値を書き換えないよう、変更不可 (frozen) にしています。
    値を変えたいときは `dataclasses.replace()` で新しいインスタンスを作ります。

    Attributes:
        uuid (str): レコードを一意に識別する ID
        name (str): 氏名 (フルネーム)
        student_number (str): 学籍番号
        email (str): 大学のメールアドレス
        grade (Grade): 学年
        discord_id (str | None): 認証済みの Discord ユーザー ID。未認証の場合は None
    """

    uuid: str
    name: str
    student_number: str
    email: str
    grade: Grade
    discord_id: str | None = None

    def to_dict(self) -> dict:
        """
        データベースへ保存するために辞書へ変換する

        Returns:
            dict: msgpack で保存できる値 (str / None) だけを持つ辞書
        """
        return {
            "uuid": self.uuid,
            "name": self.name,
            "student_number": self.student_number,
            "email": self.email,
            "grade": self.grade.value,
            "discord_id": self.discord_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StudentInfo":
        """
        データベースから読み込んだ辞書を StudentInfo に変換する

        Args:
            data (dict): `to_dict()` で作られた辞書

        Returns:
            StudentInfo: 復元した学生情報
        """
        return cls(
            uuid=data["uuid"],
            name=data["name"],
            student_number=data["student_number"],
            email=data["email"],
            grade=Grade(data["grade"]),
            discord_id=data.get("discord_id"),
        )
