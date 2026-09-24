"""
external.MailSender の偽物

実際にはメールを送らず、送った内容を記録します。
"""

from dataclasses import dataclass

from external import MailSendError


@dataclass
class SentMail:
    """
    送ったメール 1 通分の記録
    """

    to_address: str
    code: str
    expire_minutes: int


class FakeMailSender:
    """
    MailSender の偽物

    Attributes:
        sent (list[SentMail]): 送ったメール
        fail (bool): True にすると、送信時に MailSendError を送出する
    """

    def __init__(self):
        self.sent: list[SentMail] = []
        self.fail = False

    def last_code(self) -> str:
        """
        最後に送った認証コードを返す
        """
        return self.sent[-1].code

    async def send_verification_code(self, to_address: str, code: str, expire_minutes: int) -> None:
        if self.fail:
            raise MailSendError(f"{to_address} へのメール送信に失敗しました")
        self.sent.append(SentMail(to_address, code, expire_minutes))
