"""
Bot が扱う Discord ロールの定義

サーバーに作成されるロールは、すべてこのファイルで定義します。
ロールの名前や色を変えたいときは、このファイルだけを編集してください。
"""

from dataclasses import dataclass

from .grade import Grade


@dataclass(frozen=True)
class RoleDefinition:
    """
    Discord ロールの設定値

    Attributes:
        name (str): ロール名
        color (tuple[int, int, int]): ロールの色 (R, G, B)
        reason (str): ロール作成時に監査ログへ残す理由
    """

    name: str
    color: tuple[int, int, int]
    reason: str


ADMINISTRATOR_ROLE = RoleDefinition(
    name="Administrator", color=(231, 76, 60), reason="Role for administrators."
)
"""管理者ロール。このロールを持つメンバーだけが /register を実行できる"""

AUTHORIZED_ROLE = RoleDefinition(
    name="Authorized", color=(46, 204, 113), reason="Member role for authenticated members."
)
"""認証済みメンバーに付与するロール"""

UNAUTHORIZED_ROLE = RoleDefinition(
    name="Unauthorized", color=(149, 165, 166), reason="Unauthorized role for new members."
)
"""サーバーに参加したばかりの未認証メンバーに付与するロール"""

GRADE_ROLES: dict[Grade, RoleDefinition] = {
    Grade.B4: RoleDefinition("Grade:B4", (0, 112, 255), "B4 Grade Role"),
    Grade.M1: RoleDefinition("Grade:M1", (0, 176, 80), "M1 Grade Role"),
    Grade.M2: RoleDefinition("Grade:M2", (255, 192, 0), "M2 Grade Role"),
    Grade.D1: RoleDefinition("Grade:D1", (255, 0, 0), "D1 Grade Role"),
    Grade.D2: RoleDefinition("Grade:D2", (112, 48, 160), "D2 Grade Role"),
    Grade.D3: RoleDefinition("Grade:D3", (255, 0, 255), "D3 Grade Role"),
    Grade.TEACHER: RoleDefinition("Grade:TEACHER", (0, 0, 0), "Teacher Grade Role"),
    Grade.OBOG: RoleDefinition("Grade:OB/OG", (128, 128, 128), "OB/OG Grade Role"),
}
"""学年ごとに付与するロール"""

ALL_ROLES: list[RoleDefinition] = [
    ADMINISTRATOR_ROLE,
    AUTHORIZED_ROLE,
    UNAUTHORIZED_ROLE,
    *GRADE_ROLES.values(),
]
"""Bot 起動時にサーバーへ作成しておくロールの一覧"""
