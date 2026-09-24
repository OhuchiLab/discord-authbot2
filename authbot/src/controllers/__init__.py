"""
データベースや Discord API などを操作するためのインターフェースを定義・実装するパッケージ。

Bot の業務ロジックはすべてここにあります。Discord には直接依存せず、
Discord の操作は `external.DiscordGateway`、データの保存は `database.DatabaseController` を通します。

| モジュール | 内容 |
| --- | --- |
| `bot_controllers` | コントローラー一式の組み立て (`build_controllers`, `BotControllers`) |
| `onboarding_controller` | 参加から認証完了までの一連の流れ (`OnboardingController`) |
| `auth_flow_controller` | DM での対話形式の認証手続き (`AuthFlowController`) |
| `student_controller` | 学生情報の登録・照合・変更・Discord ID の紐付け (`StudentController`) |
| `student_edit_controller` | 学生情報の手動変更と Discord への反映 (`StudentEditController`) |
| `role_controller` | 認証状態に応じたロール・ニックネームの設定 (`RoleController`) |
| `year_update_controller` | 現役メンバーの年度更新 (`YearUpdateController`) |
"""

from .auth_flow_controller import AuthFlowController, AuthReply
from .bot_controllers import BotControllers, build_controllers
from .onboarding_controller import OnboardingController
from .role_controller import RoleController
from .student_controller import StudentController, StudentEditError, StudentLinkError, StudentRegistrationError
from .student_edit_controller import StudentEditController
from .year_update_controller import YearUpdateController, YearUpdateError
