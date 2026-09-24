"""
すべてのコントローラーを組み立てて、1 つにまとめる

本番 (`main.py`) でもテストでも、この `build_controllers()` で組み立てます。
テストでは、引数の `discord_gateway` や `mail_sender` に偽物を渡します。
"""

from dataclasses import dataclass

from database import DatabaseController
from external import DiscordGateway, MailSender

from .auth_flow_controller import AuthFlowController
from .onboarding_controller import OnboardingController
from .role_controller import RoleController
from .student_controller import StudentController


@dataclass(frozen=True)
class BotControllers:
    """
    Bot が使うコントローラー一式

    Attributes:
        student (StudentController): 学生情報の登録・照合
        auth_flow (AuthFlowController): DM での認証手続き
        role (RoleController): ロールの付け外し
        onboarding (OnboardingController): 参加から認証完了までの一連の流れ
    """

    student: StudentController
    auth_flow: AuthFlowController
    role: RoleController
    onboarding: OnboardingController


def build_controllers(
    database: DatabaseController,
    mail_sender: MailSender,
    discord_gateway: DiscordGateway,
    allowed_email_domain: str,
) -> BotControllers:
    """
    コントローラー一式を組み立てる

    Args:
        database (DatabaseController): 学生情報データベース
        mail_sender (MailSender): 認証コードのメール送信
        discord_gateway (DiscordGateway): Discord の操作
        allowed_email_domain (str): 受け付けるメールアドレスのドメイン

    Returns:
        BotControllers: 組み立てたコントローラー一式
    """
    student = StudentController(database, allowed_email_domain)
    auth_flow = AuthFlowController(student, mail_sender, allowed_email_domain)
    role = RoleController(discord_gateway)
    onboarding = OnboardingController(student, auth_flow, role, discord_gateway)
    return BotControllers(student=student, auth_flow=auth_flow, role=role, onboarding=onboarding)
