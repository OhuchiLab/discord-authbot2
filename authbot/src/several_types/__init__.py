"""
プロジェクト全体で使われる様々な型を定義するパッケージ。

| モジュール | 内容 |
| --- | --- |
| `grade` | 学年 (`Grade`) |
| `student_info` | データベースに保存する学生情報 (`StudentInfo`) |
| `auth_session` | DM 認証手続きの途中経過 (`AuthSession`, `AuthStep`) |
| `role_definition` | Bot が扱う Discord ロールの定義 (`RoleDefinition` と各ロール定数) |
| `year_update` | 現役メンバーの年度更新の候補と結果 (`YearUpdatePlan`, `YearUpdateCandidate`, `YearUpdateResult`) |
"""

from .auth_session import AuthSession, AuthStep
from .grade import Grade
from .role_definition import (
    ADMINISTRATOR_ROLE,
    ALL_ROLES,
    AUTHORIZED_ROLE,
    GRADE_ROLES,
    UNAUTHORIZED_ROLE,
    RoleDefinition,
)
from .student_info import StudentInfo
from .year_update import YearUpdateCandidate, YearUpdatePlan, YearUpdateResult
