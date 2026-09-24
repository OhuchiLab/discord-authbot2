"""
サーバーへの参加から認証完了までの一連の流れをまとめるコントローラー

`commands` と `events` は Discord から受け取った情報をこのクラスに渡すだけで、
「何をするか」はすべてこのクラスが決めます。
"""

import logging

from external import DiscordGateway, DiscordPermissionError, MemberNotFoundError

from .audit_log_controller import AuditLogController
from .auth_flow_controller import AuthFlowController
from .role_controller import RoleController
from .student_controller import StudentController

logger = logging.getLogger(__name__)


class OnboardingController:
    """
    メンバーの参加・DM・/auth に応じて、認証手続きとロール付与を進めるクラス
    """

    def __init__(
        self,
        student_controller: StudentController,
        auth_flow: AuthFlowController,
        role_controller: RoleController,
        discord_gateway: DiscordGateway,
        audit: AuditLogController,
    ):
        """
        コンストラクタ

        Args:
            student_controller (StudentController): 認証済みかどうかの確認に使う
            auth_flow (AuthFlowController): DM での認証手続きに使う
            role_controller (RoleController): ロールの付け外しに使う
            discord_gateway (DiscordGateway): DM の送信に使う
            audit (AuditLogController): 認証完了の記録に使う
        """
        self._students = student_controller
        self._auth_flow = auth_flow
        self._roles = role_controller
        self._discord = discord_gateway
        self._audit = audit

    async def welcome_new_member(self, user_id: str, display_name: str) -> None:
        """
        [F3 / F7] サーバーに参加したメンバーを迎える

        - 以前に認証したことがあるメンバー → 認証済みのロールをすぐに付け直す
        - 初めてのメンバー → 未認証ロールを付け、DM で認証手続きを始める

        Args:
            user_id (str): 参加したメンバーの Discord ユーザー ID
            display_name (str): 参加したメンバーの表示名
        """
        student = self._students.find_by_discord_id(user_id)
        if student is not None:
            problems = await self._roles.mark_as_authorized(user_id, student)
            await self._send_dm(
                user_id, "\n".join([f"おかえりなさい、{student.name}さん！ 認証済みのロールを付与しました。", *problems])
            )
            return

        await self._roles.mark_as_unauthorized(user_id)
        reply = self._auth_flow.start(user_id)
        await self._send_dm(user_id, f"ようこそ {display_name} さん！\n{reply.text}")

    async def receive_direct_message(self, user_id: str, text: str) -> None:
        """
        [F4 / F5] DM で届いたメッセージを認証手続きに渡し、返答を DM で送る。認証が完了したらロールを付与する

        Args:
            user_id (str): 送信者の Discord ユーザー ID
            text (str): 受け取ったメッセージ
        """
        reply = await self._auth_flow.handle_message(user_id, text)
        await self._send_dm(user_id, reply.text)

        student = reply.authenticated_student
        if student is None:
            return
        await self._audit.member_authenticated(student)

        try:
            problems = await self._roles.mark_as_authorized(user_id, student)
        except MemberNotFoundError:
            await self._send_dm(
                user_id,
                "サーバーに参加していないため、ロールを付与できませんでした。サーバーに参加すると自動で付与されます。",
            )
            return
        await self._send_dm(user_id, "\n".join(["認証が完了しました！ サーバーをご利用ください。", *problems]))

    async def request_auth(self, user_id: str) -> str:
        """
        [F6] /auth コマンドで認証を (再) 開始する

        - 認証済み → ロールとニックネームを付け直す
        - 未認証 → DM で認証手続きを始める

        Args:
            user_id (str): コマンドを実行したメンバーの Discord ユーザー ID

        Returns:
            str: コマンドの実行者に返す文章
        """
        student = self._students.find_by_discord_id(user_id)
        if student is not None:
            problems = await self._roles.mark_as_authorized(user_id, student)
            return "\n".join(["すでに認証済みです。ロールとニックネームを付け直しました。", *problems])

        reply = self._auth_flow.start(user_id)
        try:
            await self._discord.send_dm(user_id, reply.text)
        except DiscordPermissionError:
            self._auth_flow.cancel(user_id)
            return (
                "DM を送信できませんでした。"
                "サーバーのプライバシー設定で「ダイレクトメッセージ」を許可してから、もう一度実行してください。"
            )
        return "DM を送信しました。DM で質問に答えてください。"

    async def _send_dm(self, user_id: str, text: str) -> None:
        """
        DM を送る。相手が DM を拒否している場合はログに残すだけにする
        """
        try:
            await self._discord.send_dm(user_id, text)
        except DiscordPermissionError:
            logger.warning("Cannot send DM to user %s (DMs are disabled)", user_id)
