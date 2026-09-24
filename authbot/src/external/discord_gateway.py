"""
Discord API を操作する窓口 (ゲートウェイ)

Bot から Discord への操作 (DM の送信、チャンネルへの投稿、ロールの付け外し、ニックネームの変更) は、
すべてこのクラスを通して行います。
呼び出し側は Discord のオブジェクトを扱わず、「ユーザー ID (文字列)」と「ロールの定義」だけを渡します。
そのため `controllers` パッケージは Discord に依存せず、テストでは偽物 (`tests/fakes`) に差し替えられます。
"""

import logging

import discord

from several_types import RoleDefinition

logger = logging.getLogger(__name__)


class DiscordOperationError(Exception):
    """
    Discord の操作に失敗したときに送出される例外の基底クラス
    """


class GuildNotFoundError(DiscordOperationError):
    """
    Bot が対象のサーバーに参加していないときに送出される例外
    """


class MemberNotFoundError(DiscordOperationError):
    """
    対象のユーザーがサーバーに参加していないときに送出される例外
    """


class ChannelNotFoundError(DiscordOperationError):
    """
    指定した名前のテキストチャンネルがサーバーに無いときに送出される例外
    """


class DiscordPermissionError(DiscordOperationError):
    """
    Bot に権限が無い、または相手が DM を拒否しているときに送出される例外
    """


class DiscordGateway:
    """
    1 つの Discord サーバーを対象に、Discord API を操作するクラス
    """

    def __init__(self, client: discord.Client, guild_id: int):
        """
        コンストラクタ

        Args:
            client (discord.Client): ログイン済み (または、これからログインする) Bot のクライアント
            guild_id (int): 対象のサーバーの ID
        """
        self._client = client
        self._guild_id = guild_id

    async def setup_roles(self, definitions: list[RoleDefinition]) -> None:
        """
        ロールをサーバーに作成する。同じ名前のロールがすでにあれば何もしない

        Args:
            definitions (list[RoleDefinition]): 作成するロールの定義

        Raises:
            GuildNotFoundError: Bot がサーバーに参加していない場合
            DiscordPermissionError: Bot に「ロールの管理」権限が無い場合
        """
        guild = self._get_guild()
        for definition in definitions:
            await self._get_or_create_role(guild, definition)

    async def send_dm(self, user_id: str, text: str) -> None:
        """
        ユーザーに DM を送る

        Args:
            user_id (str): 送り先の Discord ユーザー ID
            text (str): 送る文章

        Raises:
            MemberNotFoundError: ユーザーが存在しない場合
            DiscordPermissionError: 相手が DM を拒否している場合
        """
        try:
            user = self._client.get_user(int(user_id)) or await self._client.fetch_user(int(user_id))
            await user.send(text)
        except discord.NotFound as error:
            raise MemberNotFoundError(f"ユーザー {user_id} が見つかりません") from error
        except discord.Forbidden as error:
            raise DiscordPermissionError(f"ユーザー {user_id} に DM を送れません") from error

    async def send_channel_message(self, channel_name: str, text: str) -> None:
        """
        サーバーのテキストチャンネルに投稿する

        本文に「<@ユーザー ID>」があっても、その人に通知が飛ばないようにして投稿します。

        Args:
            channel_name (str): 投稿先のチャンネル名 (例: "authbot-logs")
            text (str): 投稿する文章 (2000 文字まで)

        Raises:
            GuildNotFoundError: Bot がサーバーに参加していない場合
            ChannelNotFoundError: その名前のテキストチャンネルが無い場合
            DiscordPermissionError: Bot にチャンネルの閲覧・投稿の権限が無い場合
        """
        guild = self._get_guild()
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel is None:
            raise ChannelNotFoundError(f"チャンネル {channel_name} が見つかりません")
        try:
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden as error:
            raise DiscordPermissionError(f"チャンネル {channel_name} に投稿できません") from error

    async def set_nickname(self, user_id: str, nickname: str) -> None:
        """
        メンバーのニックネームを変更する

        Args:
            user_id (str): 対象の Discord ユーザー ID
            nickname (str): 新しいニックネーム

        Raises:
            GuildNotFoundError / MemberNotFoundError: サーバーまたはメンバーが見つからない場合
            DiscordPermissionError: 変更する権限が無い場合 (サーバーのオーナーや、Bot より上位のロールを持つメンバー)
        """
        member = await self._get_member(user_id)
        try:
            await member.edit(nick=nickname, reason="Authenticated")
        except discord.Forbidden as error:
            raise DiscordPermissionError(f"ユーザー {user_id} のニックネームを変更できません") from error

    async def add_roles(self, user_id: str, definitions: list[RoleDefinition]) -> None:
        """
        メンバーにロールを付与する。ロールがサーバーに無ければ作成する

        Args:
            user_id (str): 対象の Discord ユーザー ID
            definitions (list[RoleDefinition]): 付与するロール

        Raises:
            GuildNotFoundError / MemberNotFoundError: サーバーまたはメンバーが見つからない場合
            DiscordPermissionError: Bot に「ロールの管理」権限が無い、またはロールが Bot より上位の場合
        """
        member = await self._get_member(user_id)
        roles = [await self._get_or_create_role(member.guild, definition) for definition in definitions]
        try:
            await member.add_roles(*roles, reason="Authorization bot")
        except discord.Forbidden as error:
            raise DiscordPermissionError(f"ユーザー {user_id} にロールを付与できません") from error

    async def remove_roles(self, user_id: str, definitions: list[RoleDefinition]) -> None:
        """
        メンバーからロールを外す。メンバーが持っていないロールは無視する

        Args:
            user_id (str): 対象の Discord ユーザー ID
            definitions (list[RoleDefinition]): 外すロール

        Raises:
            GuildNotFoundError / MemberNotFoundError: サーバーまたはメンバーが見つからない場合
            DiscordPermissionError: Bot に「ロールの管理」権限が無い、またはロールが Bot より上位の場合
        """
        member = await self._get_member(user_id)
        names = {definition.name for definition in definitions}
        roles = [role for role in member.roles if role.name in names]
        if not roles:
            return
        try:
            await member.remove_roles(*roles, reason="Authorization bot")
        except discord.Forbidden as error:
            raise DiscordPermissionError(f"ユーザー {user_id} からロールを外せません") from error

    async def has_role(self, user_id: str, definition: RoleDefinition) -> bool:
        """
        メンバーがロールを持っているかどうかを返す

        Raises:
            GuildNotFoundError / MemberNotFoundError: サーバーまたはメンバーが見つからない場合
        """
        member = await self._get_member(user_id)
        return any(role.name == definition.name for role in member.roles)

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    def _get_guild(self) -> discord.Guild:
        """
        対象のサーバーを返す

        Raises:
            GuildNotFoundError: Bot がサーバーに参加していない場合
        """
        guild = self._client.get_guild(self._guild_id)
        if guild is None:
            raise GuildNotFoundError(f"Bot はサーバー {self._guild_id} に参加していません")
        return guild

    async def _get_member(self, user_id: str) -> discord.Member:
        """
        対象のサーバーのメンバーを返す (キャッシュ → API の順に探す)

        Raises:
            GuildNotFoundError / MemberNotFoundError: サーバーまたはメンバーが見つからない場合
        """
        guild = self._get_guild()
        member = guild.get_member(int(user_id))
        if member is not None:
            return member
        try:
            return await guild.fetch_member(int(user_id))
        except discord.NotFound as error:
            raise MemberNotFoundError(f"ユーザー {user_id} はサーバーに参加していません") from error

    async def _get_or_create_role(self, guild: discord.Guild, definition: RoleDefinition) -> discord.Role:
        """
        サーバーから名前が一致するロールを返す。無ければ作成する

        Raises:
            DiscordPermissionError: ロールを作成する権限が無い場合
        """
        role = discord.utils.get(guild.roles, name=definition.name)
        if role is not None:
            return role
        try:
            role = await guild.create_role(
                name=definition.name,
                colour=discord.Colour.from_rgb(*definition.color),
                reason=definition.reason,
            )
        except discord.Forbidden as error:
            raise DiscordPermissionError(f"ロール {definition.name} を作成できません") from error
        logger.info("Created role %s in guild %s", definition.name, guild.name)
        return role
