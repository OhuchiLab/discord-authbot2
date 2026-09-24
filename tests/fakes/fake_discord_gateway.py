"""
external.DiscordGateway の偽物

Discord に接続せず、サーバーの状態 (ロール・メンバー・送った DM) をメモリ上に記録します。
本物と同じ名前・引数のメソッドを持ち、失敗時には本物と同じ例外を送出します。
(本物と I/F が一致していることは tests/api/test_fakes_contract.py で確認しています)
"""

from collections import defaultdict
from dataclasses import dataclass, field

from external import ChannelNotFoundError, DiscordPermissionError, GuildNotFoundError, MemberNotFoundError
from several_types import RoleDefinition


@dataclass
class FakeMemberState:
    """
    偽のサーバーにいるメンバーの状態

    Attributes:
        roles (set[str]): 持っているロール名
        nickname (str | None): ニックネーム
        accepts_dm (bool): DM を受け取るかどうか (False なら DM 送信で DiscordPermissionError)
        nickname_editable (bool): Bot がニックネームを変更できるかどうか (サーバーのオーナーなら False)
    """

    roles: set[str] = field(default_factory=set)
    nickname: str | None = None
    accepts_dm: bool = True
    nickname_editable: bool = True


class FakeDiscordGateway:
    """
    DiscordGateway の偽物

    Attributes:
        guild_roles (set[str]): サーバーに存在するロール名
        members (dict[str, FakeMemberState]): サーバーのメンバー (キーは Discord ユーザー ID)
        dms (dict[str, list[str]]): ユーザーごとに送った DM
        channels (dict[str, list[str]]): サーバーにあるテキストチャンネルと、そこに投稿したメッセージ
        bot_in_guild (bool): Bot がサーバーに参加しているか (False なら GuildNotFoundError)
        can_manage_roles (bool): Bot にロールを管理する権限があるか (False なら DiscordPermissionError)
    """

    def __init__(self):
        self.guild_roles: set[str] = set()
        self.members: dict[str, FakeMemberState] = {}
        self.dms: dict[str, list[str]] = defaultdict(list)
        self.channels: dict[str, list[str]] = {}
        self.can_post_to_channels = True
        self.bot_in_guild = True
        self.can_manage_roles = True

    # ------------------------------------------------------------------
    # テストから状態を準備・確認するためのメソッド
    # ------------------------------------------------------------------

    def add_member(self, user_id: str, roles: tuple[str, ...] = (), **options) -> FakeMemberState:
        """
        サーバーにメンバーを追加する (options は FakeMemberState の属性)
        """
        member = FakeMemberState(roles=set(roles), **options)
        self.members[user_id] = member
        return member

    def add_channel(self, name: str) -> None:
        """
        サーバーにテキストチャンネルを追加する
        """
        self.channels.setdefault(name, [])

    def last_dm(self, user_id: str) -> str:
        """
        ユーザーに最後に送った DM を返す
        """
        return self.dms[user_id][-1]

    # ------------------------------------------------------------------
    # DiscordGateway と同じ I/F
    # ------------------------------------------------------------------

    async def setup_roles(self, definitions: list[RoleDefinition]) -> None:
        self._check_guild()
        self._check_manage_roles()
        self.guild_roles |= {definition.name for definition in definitions}

    async def send_dm(self, user_id: str, text: str) -> None:
        member = self.members.get(user_id)
        if member is not None and not member.accepts_dm:
            raise DiscordPermissionError(f"ユーザー {user_id} に DM を送れません")
        self.dms[user_id].append(text)

    async def send_channel_message(self, channel_name: str, text: str) -> None:
        self._check_guild()
        if channel_name not in self.channels:
            raise ChannelNotFoundError(f"チャンネル {channel_name} が見つかりません")
        if not self.can_post_to_channels:
            raise DiscordPermissionError(f"チャンネル {channel_name} に投稿できません")
        self.channels[channel_name].append(text)

    async def set_nickname(self, user_id: str, nickname: str) -> None:
        member = self._get_member(user_id)
        if not member.nickname_editable:
            raise DiscordPermissionError(f"ユーザー {user_id} のニックネームを変更できません")
        member.nickname = nickname

    async def add_roles(self, user_id: str, definitions: list[RoleDefinition]) -> None:
        member = self._get_member(user_id)
        self._check_manage_roles()
        names = {definition.name for definition in definitions}
        self.guild_roles |= names
        member.roles |= names

    async def remove_roles(self, user_id: str, definitions: list[RoleDefinition]) -> None:
        member = self._get_member(user_id)
        names = {definition.name for definition in definitions} & member.roles
        if not names:
            return
        self._check_manage_roles()
        member.roles -= names

    async def has_role(self, user_id: str, definition: RoleDefinition) -> bool:
        return definition.name in self._get_member(user_id).roles

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    def _check_guild(self) -> None:
        if not self.bot_in_guild:
            raise GuildNotFoundError("Bot はサーバーに参加していません")

    def _check_manage_roles(self) -> None:
        if not self.can_manage_roles:
            raise DiscordPermissionError("ロールを管理する権限がありません")

    def _get_member(self, user_id: str) -> FakeMemberState:
        self._check_guild()
        if user_id not in self.members:
            raise MemberNotFoundError(f"ユーザー {user_id} はサーバーに参加していません")
        return self.members[user_id]
