"""
SMTP サーバーを使って認証コードのメールを送信する
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class MailSendError(Exception):
    """
    メールの送信に失敗したときに送出される例外
    """


class MailSender:
    """
    認証コードのメールを送信するクラス

    (Gmail の場合: ホスト smtp.gmail.com / ポート 587 / STARTTLS あり / アプリパスワードでログイン)
    (テスト用の Mailpit の場合: ホスト localhost / ポート 1025 / STARTTLS なし / ログインなし)
    """

    def __init__(
        self,
        host: str,
        port: int,
        mail_from: str,
        user: str | None = None,
        password: str | None = None,
        use_starttls: bool = True,
    ):
        """
        コンストラクタ

        Args:
            host (str): SMTP サーバーのホスト名
            port (int): SMTP サーバーのポート番号
            mail_from (str): 差出人のメールアドレス
            user (str | None): ログインユーザー名。None ならログインしない
            password (str | None): ログインパスワード
            use_starttls (bool): STARTTLS で通信を暗号化するかどうか
        """
        self._host = host
        self._port = port
        self._mail_from = mail_from
        self._user = user
        self._password = password
        self._use_starttls = use_starttls

    async def send_verification_code(self, to_address: str, code: str, expire_minutes: int) -> None:
        """
        認証コードを記載したメールを送信する

        SMTP 通信は時間がかかるため、Bot 全体が止まらないよう別スレッドで実行します。

        Args:
            to_address (str): 宛先のメールアドレス
            code (str): 認証コード
            expire_minutes (int): 認証コードの有効期限 (分)。本文に記載する

        Raises:
            MailSendError: 送信に失敗した場合
        """
        message = EmailMessage()
        message["Subject"] = "【大内研究室 Discord】認証コードのお知らせ"
        message["From"] = self._mail_from
        message["To"] = to_address
        message.set_content(
            "大内研究室 Discord サーバーの認証コードをお知らせします。\n"
            "\n"
            f"    認証コード: {code}\n"
            "\n"
            "この認証コードを Discord の Bot への DM で送信してください。\n"
            f"有効期限は {expire_minutes} 分です。\n"
            "\n"
            "このメールに心当たりがない場合は、破棄してください。\n"
        )

        try:
            await asyncio.to_thread(self._send, message)
        except (smtplib.SMTPException, OSError) as error:
            raise MailSendError(f"{to_address} へのメール送信に失敗しました") from error
        logger.info("Sent verification code to %s", to_address)

    def _send(self, message: EmailMessage) -> None:
        """
        SMTP サーバーに接続してメールを 1 通送信する (ブロッキング処理)
        """
        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            if self._use_starttls:
                smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password or "")
            smtp.send_message(message)
