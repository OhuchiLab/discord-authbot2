"""
現役メンバーの年度更新で使うデータクラス定義
"""

from dataclasses import dataclass, field

from .grade import Grade


@dataclass
class YearUpdateCandidate:
    """
    年度更新での、学生 1 人分の更新候補

    Attributes:
        student_uuid (str): 学生情報の uuid
        name (str): 氏名 (確認画面の表示用)
        discord_id (str | None): Discord ユーザー ID。未認証なら None
        current_grade (Grade): 今の学年
        default_next_grade (Grade): 通常の進級規則による更新先
        next_grade (Grade): 更新先。管理者が確認画面で変更できる
    """

    student_uuid: str
    name: str
    discord_id: str | None
    current_grade: Grade
    default_next_grade: Grade
    next_grade: Grade

    @property
    def is_changed(self) -> bool:
        """管理者が更新先を通常の進級規則から変更したかどうか"""
        return self.next_grade != self.default_next_grade


@dataclass
class YearUpdatePlan:
    """
    年度更新の計画 (更新候補の一覧)

    確定されるまでは、学生情報にも Discord のロールにも反映されません。

    Attributes:
        fiscal_year (int): 対象年度 (例: 2027)
        candidates (list[YearUpdateCandidate]): 更新候補
    """

    fiscal_year: int
    candidates: list[YearUpdateCandidate] = field(default_factory=list)

    def find(self, student_uuid: str) -> YearUpdateCandidate:
        """
        uuid が一致する更新候補を返す

        Raises:
            KeyError: 見つからない場合
        """
        for candidate in self.candidates:
            if candidate.student_uuid == student_uuid:
                return candidate
        raise KeyError(student_uuid)


@dataclass(frozen=True)
class YearUpdateResult:
    """
    年度更新を確定した結果

    Attributes:
        fiscal_year (int): 対象年度
        updated_count (int): 学生情報を更新した人数
        synced_count (int): Discord のロールを同期した人数
        not_in_server (list[str]): 認証済みだがサーバーにいないため、ロールを同期できなかった学生の氏名
        problems (list[str]): ロールの同期でうまくいかなかった処理の説明
    """

    fiscal_year: int
    updated_count: int
    synced_count: int
    not_in_server: list[str]
    problems: list[str]
