"""
メンバーの認証状態に応じて、Discord のロールとニックネームを設定するコントローラー
"""

import logging

from external import DiscordGateway, DiscordPermissionError, GuildNotFoundError, MemberNotFoundError
from several_types import (
    ADMINISTRATOR_ROLE,
    ALL_ROLES,
    AUTHORIZED_ROLE,
    GRADE_ROLES,
    UNAUTHORIZED_ROLE,
    StudentInfo,
)

logger = logging.getLogger(__name__)

ROLE_PERMISSION_PROBLEM = "ロールを付与できませんでした。管理者に連絡してください。"
"""ロールを付け外しできなかったときに、ユーザーに表示する説明"""


class RoleController:
    """
    ロールに関する業務ルールをまとめたクラス

    「どのロールを付ける/外すか」はこのクラスが決め、
    Discord への実際の操作は `external.DiscordGateway` に任せます。
    """

    def __init__(self, discord_gateway: DiscordGateway):
        """
        コンストラクタ

        Args:
            discord_gateway (DiscordGateway): Discord の操作に使う
        """
        self._discord = discord_gateway

    async def setup_roles(self) -> None:
        """
        Bot が使うロール (`several_types.ALL_ROLES`) をサーバーに作成する。作成済みのものはそのまま

        失敗してもログに残すだけで、Bot は動き続けます。
        """
        try:
            await self._discord.setup_roles(ALL_ROLES)
        except GuildNotFoundError:
            logger.error("Bot is not a member of the target guild. Invite the bot to the server.")
        except DiscordPermissionError:
            logger.error("No permission to create roles. Grant 'Manage Roles' to the bot.")

    async def mark_as_unauthorized(self, user_id: str) -> None:
        """
        メンバーに未認証 (Unauthorized) ロールを付与する。失敗してもログに残すだけ

        Args:
            user_id (str): 対象の Discord ユーザー ID
        """
        try:
            await self._discord.add_roles(user_id, [UNAUTHORIZED_ROLE])
        except DiscordPermissionError:
            logger.error("No permission to add Unauthorized role to user %s", user_id)

    async def mark_as_authorized(self, user_id: str, student: StudentInfo) -> list[str]:
        """
        メンバーを認証済みの状態にする

        1. ニックネームを学生情報の氏名に変更する
        2. 認証済み (Authorized) ロールを付け、未認証 (Unauthorized) ロールを外す
        3. 学年ロールを学生情報に合わせる (`sync_grade_role()`)

        権限不足で失敗した処理があっても、残りの処理は続けます。

        Args:
            user_id (str): 対象の Discord ユーザー ID
            student (StudentInfo): メンバーの学生情報

        Returns:
            list[str]: うまくいかなかった処理の説明 (ユーザーに表示する)。すべて成功したら空のリスト

        Raises:
            MemberNotFoundError: メンバーがサーバーに参加していない場合
        """
        problems: list[str] = []

        try:
            await self._discord.set_nickname(user_id, student.name)
        except DiscordPermissionError:
            logger.warning("No permission to change nickname of user %s", user_id)
            problems.append(
                "ニックネームを変更できませんでした。(サーバーのオーナーや、Bot より上位のロールを持つメンバーは変更できません)"
            )

        try:
            await self._discord.add_roles(user_id, [AUTHORIZED_ROLE])
            await self._discord.remove_roles(user_id, [UNAUTHORIZED_ROLE])
        except DiscordPermissionError:
            logger.error("No permission to update roles of user %s", user_id)
            problems.append(ROLE_PERMISSION_PROBLEM)
            return problems

        problems += await self.sync_grade_role(user_id, student)
        return problems

    async def sync_grade_role(self, user_id: str, student: StudentInfo) -> list[str]:
        """
        メンバーの学年ロールを、学生情報の学年に合わせる (ニックネームなど他は変更しない)

        学生情報の学年のロールだけを付け、他の学年のロールは外します。
        卒業・修了した学生 (学年が OB/OG) は、学年ロールが外れて OB/OG ロールが付きます。

        Args:
            user_id (str): 対象の Discord ユーザー ID
            student (StudentInfo): メンバーの学生情報

        Returns:
            list[str]: うまくいかなかった処理の説明 (ユーザーに表示する)。成功したら空のリスト

        Raises:
            MemberNotFoundError: メンバーがサーバーに参加していない場合
        """
        grade_role = GRADE_ROLES[student.grade]
        other_grade_roles = [role for role in GRADE_ROLES.values() if role != grade_role]
        try:
            await self._discord.add_roles(user_id, [grade_role])
            await self._discord.remove_roles(user_id, other_grade_roles)
        except DiscordPermissionError:
            logger.error("No permission to update grade roles of user %s", user_id)
            return [ROLE_PERMISSION_PROBLEM]
        return []

    async def revoke_authorization(self, user_id: str) -> list[str]:
        """
        メンバーを未認証の状態に戻す (Discord アカウントとの紐付けを解除したとき)

        認証済み (Authorized) ロールと学年ロールを外し、未認証 (Unauthorized) ロールを付けます。
        それ以外のロールとニックネームは変更しません。

        Args:
            user_id (str): 対象の Discord ユーザー ID

        Returns:
            list[str]: うまくいかなかった処理の説明。成功したら空のリスト

        Raises:
            MemberNotFoundError: メンバーがサーバーに参加していない場合
        """
        try:
            await self._discord.remove_roles(user_id, [AUTHORIZED_ROLE, *GRADE_ROLES.values()])
            await self._discord.add_roles(user_id, [UNAUTHORIZED_ROLE])
        except DiscordPermissionError:
            logger.error("No permission to revoke roles of user %s", user_id)
            return [ROLE_PERMISSION_PROBLEM]
        return []

    async def is_admin(self, user_id: str) -> bool:
        """
        メンバーが管理者 (Administrator ロールを持つ) かどうかを判定する

        Args:
            user_id (str): 対象の Discord ユーザー ID

        Returns:
            bool: 管理者であれば True。サーバーに参加していなければ False
        """
        try:
            return await self._discord.has_role(user_id, ADMINISTRATOR_ROLE)
        except (GuildNotFoundError, MemberNotFoundError):
            return False
