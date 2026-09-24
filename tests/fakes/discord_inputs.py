"""
Discord から Bot に渡されるオブジェクト (メンバー・メッセージ・インタラクション) の偽物

機能テストで、`AuthBot.on_member_join()` や `on_message()`、スラッシュコマンドの処理に渡します。
Bot が実際に使う属性・メソッドだけを持っています。
"""

from dataclasses import dataclass, field


@dataclass
class FakeGuild:
    id: int


@dataclass
class FakeUser:
    id: int
    display_name: str = "テストユーザー"
    bot: bool = False


@dataclass
class FakeDiscordMember(FakeUser):
    """on_member_join に渡すメンバー"""

    guild: FakeGuild = field(default_factory=lambda: FakeGuild(0))


@dataclass
class FakeDiscordMessage:
    """on_message に渡すメッセージ。guild が None なら DM"""

    author: FakeUser
    content: str
    guild: FakeGuild | None = None


@dataclass
class SentResponse:
    """インタラクションへの応答 1 件分の記録"""

    text: str | None
    ephemeral: bool


class FakeInteractionResponse:
    def __init__(self, sent: list[SentResponse]):
        self._sent = sent
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, text: str, ephemeral: bool = False) -> None:
        self._done = True
        self._sent.append(SentResponse(text, ephemeral))

    async def defer(self, ephemeral: bool = False, thinking: bool = False) -> None:
        self._done = True


class FakeFollowup:
    def __init__(self, sent: list[SentResponse]):
        self._sent = sent

    async def send(self, text: str, ephemeral: bool = False) -> None:
        self._sent.append(SentResponse(text, ephemeral))


class FakeInteraction:
    """
    スラッシュコマンドの処理に渡すインタラクション

    Attributes:
        sent (list[SentResponse]): コマンドの実行者に返した応答
    """

    def __init__(self, user: FakeUser, guild: FakeGuild):
        self.user = user
        self.guild = guild
        self.command = None
        self.sent: list[SentResponse] = []
        self.response = FakeInteractionResponse(self.sent)
        self.followup = FakeFollowup(self.sent)
