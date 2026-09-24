"""
学生情報の手動変更・削除で使うデータクラス定義
"""

from dataclasses import dataclass

from .student_info import StudentInfo

FIELD_LABELS: dict[str, str] = {
    "name": "氏名",
    "student_number": "学籍番号",
    "grade": "学年",
    "email": "メールアドレス",
    "discord_id": "Discord との紐付け",
}
"""StudentInfo の項目名と、画面に表示する名前"""


def describe_value(student: StudentInfo, field: str) -> str:
    """
    学生情報の 1 項目を、画面やログに表示する文字列にする (学年は "B4"、Discord は "<@ID>" か "なし (未認証)")
    """
    if field == "grade":
        return student.grade.value
    if field == "discord_id":
        return f"<@{student.discord_id}>" if student.discord_id else "なし (未認証)"
    return str(getattr(student, field))


@dataclass(frozen=True)
class StudentEdit:
    """
    学生情報の変更内容 (変更前と変更後)

    確定されるまでは、学生情報にも Discord にも反映されません。

    Attributes:
        before (StudentInfo): 変更前の学生情報
        after (StudentInfo): 変更後の学生情報
    """

    before: StudentInfo
    after: StudentInfo

    def changed_fields(self) -> list[str]:
        """
        変更される項目の表示名を返す (例: ["氏名", "学年"])
        """
        return [
            label for field, label in FIELD_LABELS.items() if getattr(self.before, field) != getattr(self.after, field)
        ]

    def describe_changes(self) -> list[str]:
        """
        変更される項目を「項目名: 変更前 → 変更後」の形で返す (例: ["学年: B4 → M1"])
        """
        return [
            f"{label}: {describe_value(self.before, field)} → {describe_value(self.after, field)}"
            for field, label in FIELD_LABELS.items()
            if getattr(self.before, field) != getattr(self.after, field)
        ]

    @property
    def unlinks_discord(self) -> bool:
        """Discord アカウントとの紐付けを解除する変更かどうか"""
        return self.before.discord_id is not None and self.after.discord_id is None


@dataclass(frozen=True)
class StudentEditResult:
    """
    学生情報の変更を確定した結果

    Attributes:
        student (StudentInfo): 変更後の学生情報
        discord_synced (bool): Discord のニックネーム・ロールを変更したかどうか
        not_in_server (bool): 認証済みだがサーバーにいないため、Discord に反映できなかったかどうか
        problems (list[str]): Discord への反映でうまくいかなかった処理の説明
    """

    student: StudentInfo
    discord_synced: bool
    not_in_server: bool
    problems: list[str]


@dataclass(frozen=True)
class StudentDeleteResult:
    """
    学生情報の削除を確定した結果

    Attributes:
        student (StudentInfo): 削除した学生情報
        discord_synced (bool): Discord 上で未認証の状態に戻したかどうか
        not_in_server (bool): 認証済みだがサーバーにいないため、Discord は変更しなかったかどうか
        problems (list[str]): Discord の変更でうまくいかなかった処理の説明
    """

    student: StudentInfo
    discord_synced: bool
    not_in_server: bool
    problems: list[str]
