"""
[単体] external.MailSender のテスト

smtplib.SMTP を偽物に置き換えて、「接続手順 (STARTTLS・ログイン)」と「メールの内容」を確認します。
実際の SMTP サーバーとのやり取りは APIテスト (tests/api/test_external_api.py) で確認します。
"""

import smtplib

import pytest

import external.mail_sender
from external import MailSender, MailSendError


class FakeSMTP:
    """smtplib.SMTP の偽物。呼ばれた操作を記録する"""

    instances: list["FakeSMTP"] = []
    fail_on_send = False

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.calls: list[str] = []
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(f"login:{user}:{password}")

    def send_message(self, message):
        if FakeSMTP.fail_on_send:
            raise smtplib.SMTPRecipientsRefused({})
        self.calls.append("send_message")
        self.messages.append(message)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    FakeSMTP.fail_on_send = False
    monkeypatch.setattr(external.mail_sender.smtplib, "SMTP", FakeSMTP)


async def test_STARTTLSとログインをしてから送信する():
    sender = MailSender("smtp.example.com", 587, "bot@example.com", user="bot", password="secret")
    await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)

    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.example.com", 587)
    assert smtp.calls == ["starttls", "login:bot:secret", "send_message"]


async def test_設定によりSTARTTLSとログインを省略する():
    sender = MailSender("localhost", 1025, "bot@example.com", use_starttls=False)
    await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)
    assert FakeSMTP.instances[0].calls == ["send_message"]


async def test_メールに宛先_差出人_認証コード_有効期限が書かれている():
    sender = MailSender("localhost", 1025, "bot@example.com", use_starttls=False)
    await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)

    message = FakeSMTP.instances[0].messages[0]
    assert message["To"] == "yamada@shizuoka.ac.jp"
    assert message["From"] == "bot@example.com"
    body = message.get_content()
    assert "123456" in body
    assert "10 分" in body


async def test_送信に失敗したら_MailSendError():
    FakeSMTP.fail_on_send = True
    sender = MailSender("localhost", 1025, "bot@example.com", use_starttls=False)
    with pytest.raises(MailSendError):
        await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)
