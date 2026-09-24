"""
テスト用のローカル SMTP サーバー

Bot が送った認証メールを、実際には配送せずに画面に表示します。
(scripts/run_local_test.sh から起動されます。単体で使う場合: python scripts/local_mail_server.py 1025)
"""

import sys
import time
from email import message_from_bytes, policy

from aiosmtpd.controller import Controller


class PrintHandler:
    """受け取ったメールの宛先・件名・本文を表示する"""

    async def handle_DATA(self, server, session, envelope):
        mail = message_from_bytes(envelope.content, policy=policy.default)
        print(
            "\n"
            "================ [テスト用メールサーバー] メールを受け取りました ================\n"
            f"宛先: {', '.join(envelope.rcpt_tos)}\n"
            f"件名: {mail['Subject']}\n"
            "--------------------------------------------------------------------------------\n"
            f"{mail.get_content()}"
            "================================================================================\n",
            flush=True,
        )
        return "250 OK"


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 1025
    controller = Controller(PrintHandler(), hostname="127.0.0.1", port=port)
    controller.start()
    print(f"[テスト用メールサーバー] 127.0.0.1:{port} で待ち受けています", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
