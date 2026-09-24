"""
[API] external パッケージの公開 I/F のテスト

MailSender は、テスト中だけローカルに立てた SMTP サーバー (aiosmtpd) に実際にメールを送り、
SMTP の手順どおりに送信できることを確認します。

DiscordGateway は本物の Discord が必要なため、ここではテストしません (システムテストで確認します)。
"""

import socket
from email import message_from_bytes, policy

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

from external import MailSender, MailSendError


class RecordingHandler:
    """受け取ったメールを記録する SMTP サーバーの処理"""

    def __init__(self):
        self.envelopes = []

    async def handle_DATA(self, server, session, envelope):
        self.envelopes.append(envelope)
        return "250 OK"


def accept_only_bot(server, session, envelope, mechanism, auth_data):
    """ユーザー名 bot / パスワード secret だけを受け付ける認証処理"""
    ok = isinstance(auth_data, LoginPassword) and auth_data.login == b"bot" and auth_data.password == b"secret"
    # handled=False: 失敗時の応答 (535) を aiosmtpd に送らせる
    return AuthResult(success=ok, handled=False)


def find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def smtp_server():
    """テスト中だけ動くローカルの SMTP サーバー (ログインあり・TLS なし)"""
    handler = RecordingHandler()
    controller = Controller(
        handler,
        hostname="127.0.0.1",
        port=find_free_port(),
        authenticator=accept_only_bot,
        auth_require_tls=False,
    )
    controller.start()
    yield controller, handler
    controller.stop()


async def test_SMTPサーバーにメールが届く(smtp_server):
    controller, handler = smtp_server
    sender = MailSender("127.0.0.1", controller.port, "bot@example.com", use_starttls=False)

    await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)

    envelope = handler.envelopes[0]
    assert envelope.mail_from == "bot@example.com"
    assert envelope.rcpt_tos == ["yamada@shizuoka.ac.jp"]
    mail = message_from_bytes(envelope.content, policy=policy.default)
    assert mail["Subject"] == "【大内研究室 Discord】認証コードのお知らせ"
    assert "認証コード: 123456" in mail.get_content()


async def test_ログインしてから送信できる(smtp_server):
    controller, handler = smtp_server
    sender = MailSender("127.0.0.1", controller.port, "bot@example.com", user="bot", password="secret", use_starttls=False)

    await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)

    assert len(handler.envelopes) == 1


async def test_ログインに失敗したら_MailSendError(smtp_server):
    controller, _ = smtp_server
    sender = MailSender("127.0.0.1", controller.port, "bot@example.com", user="bot", password="wrong", use_starttls=False)

    with pytest.raises(MailSendError):
        await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)


async def test_SMTPサーバーに接続できなければ_MailSendError():
    sender = MailSender("127.0.0.1", find_free_port(), "bot@example.com", use_starttls=False)

    with pytest.raises(MailSendError):
        await sender.send_verification_code("yamada@shizuoka.ac.jp", "123456", 10)
