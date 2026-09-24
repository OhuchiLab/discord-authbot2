"""
[単体] external.DiscordGateway のテスト

Discord には接続せず、discord.py のオブジェクト (Client / Guild / Member / Role) を
必要な属性だけ持つ偽物に置き換えて、「discord.py の呼び方」と「例外の変換」を確認します。
"""

from dataclasses import dataclass, field

import discord
import pytest

from external import ChannelNotFoundError, DiscordGateway, DiscordPermissionError, GuildNotFoundError, MemberNotFoundError
from several_types import AUTHORIZED_ROLE, UNAUTHORIZED_ROLE

GUILD_ID = 1000
USER_ID = 111


class _ErrorResponse:
    """discord.Forbidden / discord.NotFound を作るために必要な HTTP 応答の偽物"""

    def __init__(self, status: int):
        self.status = status
        self.reason = "error"


def forbidden() -> discord.Forbidden:
    return discord.Forbidden(_ErrorResponse(403), "Missing Permissions")


def not_found() -> discord.NotFound:
    return discord.NotFound(_ErrorResponse(404), "Unknown Member")


@dataclass(eq=False)
class FakeRole:
    name: str


@dataclass(eq=False)
class FakeMember:
    guild: "FakeGuild"
    roles: list[FakeRole] = field(default_factory=list)
    nick: str | None = None
    forbidden: bool = False

    async def edit(self, nick, reason):
        if self.forbidden:
            raise forbidden()
        self.nick = nick

    async def add_roles(self, *roles, reason):
        if self.forbidden:
            raise forbidden()
        self.roles.extend(role for role in roles if role not in self.roles)

    async def remove_roles(self, *roles, reason):
        if self.forbidden:
            raise forbidden()
        self.roles = [role for role in self.roles if role not in roles]


@dataclass(eq=False)
class FakeTextChannel:
    name: str
    forbidden: bool = False
    sent: list[tuple[str, object]] = field(default_factory=list)

    async def send(self, text, allowed_mentions):
        if self.forbidden:
            raise forbidden()
        self.sent.append((text, allowed_mentions))


@dataclass(eq=False)
class FakeGuild:
    name: str = "test-guild"
    roles: list[FakeRole] = field(default_factory=list)
    text_channels: list[FakeTextChannel] = field(default_factory=list)
    members: dict[int, FakeMember] = field(default_factory=dict)
    can_create_role: bool = True

    async def create_role(self, name, colour, reason):
        if not self.can_create_role:
            raise forbidden()
        role = FakeRole(name)
        self.roles.append(role)
        return role

    def get_member(self, user_id):
        return None  # キャッシュには無い想定で、fetch_member を通す

    async def fetch_member(self, user_id):
        if user_id not in self.members:
            raise not_found()
        return self.members[user_id]


@dataclass(eq=False)
class FakeUser:
    accepts_dm: bool = True
    received: list[str] = field(default_factory=list)

    async def send(self, text):
        if not self.accepts_dm:
            raise forbidden()
        self.received.append(text)


class FakeClient:
    def __init__(self, guild: FakeGuild | None, users: dict[int, FakeUser] | None = None):
        self._guild = guild
        self._users = users or {}

    def get_guild(self, guild_id):
        return self._guild if guild_id == GUILD_ID else None

    def get_user(self, user_id):
        return None  # キャッシュには無い想定で、fetch_user を通す

    async def fetch_user(self, user_id):
        if user_id not in self._users:
            raise not_found()
        return self._users[user_id]


@pytest.fixture
def guild() -> FakeGuild:
    return FakeGuild()


@pytest.fixture
def member(guild) -> FakeMember:
    member = FakeMember(guild)
    guild.members[USER_ID] = member
    return member


def gateway_for(guild: FakeGuild | None, users: dict[int, FakeUser] | None = None) -> DiscordGateway:
    return DiscordGateway(FakeClient(guild, users), GUILD_ID)


def role_names(member: FakeMember) -> set[str]:
    return {role.name for role in member.roles}


async def test_setup_rolesは無いロールだけを作成する(guild):
    existing = FakeRole(AUTHORIZED_ROLE.name)
    guild.roles.append(existing)

    await gateway_for(guild).setup_roles([AUTHORIZED_ROLE, UNAUTHORIZED_ROLE])

    assert [role.name for role in guild.roles] == [AUTHORIZED_ROLE.name, UNAUTHORIZED_ROLE.name]
    assert guild.roles[0] is existing


async def test_Botがサーバーにいなければ_GuildNotFoundError():
    with pytest.raises(GuildNotFoundError):
        await gateway_for(None).setup_roles([AUTHORIZED_ROLE])


async def test_ロールを作成できなければ_DiscordPermissionError(guild):
    guild.can_create_role = False
    with pytest.raises(DiscordPermissionError):
        await gateway_for(guild).setup_roles([AUTHORIZED_ROLE])


async def test_add_rolesはロールを作成して付与する(guild, member):
    await gateway_for(guild).add_roles(str(USER_ID), [AUTHORIZED_ROLE])
    assert role_names(member) == {AUTHORIZED_ROLE.name}


async def test_remove_rolesは持っているロールだけを外す(guild, member):
    authorized = FakeRole(AUTHORIZED_ROLE.name)
    guild.roles.append(authorized)
    member.roles.append(authorized)

    await gateway_for(guild).remove_roles(str(USER_ID), [AUTHORIZED_ROLE, UNAUTHORIZED_ROLE])

    assert member.roles == []


async def test_メンバーがいなければ_MemberNotFoundError(guild):
    with pytest.raises(MemberNotFoundError):
        await gateway_for(guild).set_nickname(str(USER_ID), "山田 太郎")


async def test_権限が無ければ_DiscordPermissionError(guild, member):
    member.forbidden = True
    gateway = gateway_for(guild)
    with pytest.raises(DiscordPermissionError):
        await gateway.set_nickname(str(USER_ID), "山田 太郎")
    with pytest.raises(DiscordPermissionError):
        await gateway.add_roles(str(USER_ID), [AUTHORIZED_ROLE])


async def test_has_roleはロール名で判定する(guild, member):
    member.roles.append(FakeRole(AUTHORIZED_ROLE.name))
    gateway = gateway_for(guild)
    assert await gateway.has_role(str(USER_ID), AUTHORIZED_ROLE)
    assert not await gateway.has_role(str(USER_ID), UNAUTHORIZED_ROLE)


async def test_send_dmはユーザーにDMを送る(guild):
    user = FakeUser()
    await gateway_for(guild, {USER_ID: user}).send_dm(str(USER_ID), "こんにちは")
    assert user.received == ["こんにちは"]


async def test_DMを拒否されたら_DiscordPermissionError(guild):
    with pytest.raises(DiscordPermissionError):
        await gateway_for(guild, {USER_ID: FakeUser(accepts_dm=False)}).send_dm(str(USER_ID), "こんにちは")


async def test_存在しないユーザーへのDMは_MemberNotFoundError(guild):
    with pytest.raises(MemberNotFoundError):
        await gateway_for(guild).send_dm(str(USER_ID), "こんにちは")


async def test_名前が一致するチャンネルに_メンションで通知せずに投稿する(guild):
    channel = FakeTextChannel("authbot-logs")
    guild.text_channels.append(channel)

    await gateway_for(guild).send_channel_message("authbot-logs", "<@1> が登録しました")

    text, allowed_mentions = channel.sent[0]
    assert text == "<@1> が登録しました"
    assert allowed_mentions.users is False and allowed_mentions.roles is False and allowed_mentions.everyone is False


async def test_チャンネルが無ければ_ChannelNotFoundError(guild):
    with pytest.raises(ChannelNotFoundError):
        await gateway_for(guild).send_channel_message("authbot-logs", "テスト")


async def test_チャンネルに投稿する権限が無ければ_DiscordPermissionError(guild):
    guild.text_channels.append(FakeTextChannel("authbot-logs", forbidden=True))
    with pytest.raises(DiscordPermissionError):
        await gateway_for(guild).send_channel_message("authbot-logs", "テスト")
