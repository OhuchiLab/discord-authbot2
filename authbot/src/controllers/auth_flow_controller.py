"""
DM での対話形式の認証手続きを進めるコントローラー

このモジュールは Discord に依存しません。
「ユーザー ID と受け取ったメッセージ」から「返信する文章」を決めるだけで、
実際のメッセージ送信やロールの付与は `events` パッケージが行います。

手続きの流れ:

    氏名 → 学籍番号 → 学年 → メールアドレス → (照合 & 認証コードをメール送信) → 認証コード → 完了
"""

import asyncio
import logging
import secrets
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from external import MailSender, MailSendError
from several_types import AuthSession, AuthStep, Grade, StudentInfo
from utils import is_valid_email, is_valid_student_number, normalize_input

from .student_controller import StudentController, StudentLinkError

logger = logging.getLogger(__name__)

CODE_EXPIRE_MINUTES = 10
"""認証コードの有効期限 (分)"""

MAX_CODE_ATTEMPTS = 5
"""認証コードを間違えられる回数。これを超えると最初からやり直し"""

RESTART_KEYWORDS = {"やり直し", "やりなおし", "リセット", "RESET"}
"""このいずれかが送られてきたら、手続きを最初からやり直す (大文字・小文字は区別しない)"""


@dataclass
class AuthReply:
    """
    認証フローからの返答

    Attributes:
        messages (list[str]): ユーザーへ送る文章 (1 通にまとめて送信する)
        authenticated_student (StudentInfo | None): 今回のメッセージで認証が完了した場合、その学生情報
    """

    messages: list[str]
    authenticated_student: StudentInfo | None = None

    @property
    def text(self) -> str:
        """
        送信用に、messages を改行でつないだ文章
        """
        return "\n".join(self.messages)


def generate_code() -> str:
    """
    6 桁の数字の認証コードを生成する (推測されにくい乱数を使用)
    """
    return f"{secrets.randbelow(1_000_000):06d}"


class AuthFlowController:
    """
    ユーザーごとの認証手続きの状態 (`AuthSession`) を管理し、手続きを 1 段階ずつ進めるクラス
    """

    def __init__(
        self,
        student_controller: StudentController,
        mail_sender: MailSender,
        allowed_email_domain: str,
        now: Callable[[], datetime] = datetime.now,
        code_generator: Callable[[], str] = generate_code,
    ):
        """
        コンストラクタ

        Args:
            student_controller (StudentController): 学生情報の照合・紐付けに使う
            mail_sender (MailSender): 認証コードのメール送信に使う
            allowed_email_domain (str): 受け付けるメールアドレスのドメイン
            now (Callable[[], datetime]): 現在時刻を返す関数 (テストで差し替えるため)
            code_generator (Callable[[], str]): 認証コードを生成する関数 (テストで差し替えるため)
        """
        self._student_controller = student_controller
        self._mail_sender = mail_sender
        self._allowed_email_domain = allowed_email_domain
        self._now = now
        self._generate_code = code_generator
        self._sessions: dict[str, AuthSession] = {}
        # 同じユーザーのメッセージを 1 通ずつ順番に処理するためのロック
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def start(self, user_id: str) -> AuthReply:
        """
        認証手続きを (最初から) 開始する

        Args:
            user_id (str): Discord ユーザー ID

        Returns:
            AuthReply: 最初の質問 (氏名) を含む返答
        """
        self._sessions[user_id] = AuthSession()
        return AuthReply(
            [
                "大内研究室 Discord 認証 Bot です！",
                "認証のため、いくつか質問します。途中で「やり直し」と送ると最初からやり直せます。",
                "",
                "名前 (フルネーム) を教えてください。",
            ]
        )

    def cancel(self, user_id: str) -> None:
        """
        認証手続きを中止する (途中経過を破棄する)
        """
        self._sessions.pop(user_id, None)

    async def handle_message(self, user_id: str, text: str) -> AuthReply:
        """
        ユーザーから DM で届いたメッセージを処理し、返答を決める

        Args:
            user_id (str): Discord ユーザー ID
            text (str): 受け取ったメッセージ

        Returns:
            AuthReply: ユーザーへの返答
        """
        async with self._locks[user_id]:
            text = normalize_input(text)
            session = self._sessions.get(user_id)

            if session is None:
                if self._student_controller.find_by_discord_id(user_id) is not None:
                    return AuthReply(["すでに認証済みです。"])
                return self.start(user_id)

            if text.upper() in RESTART_KEYWORDS:
                return self.start(user_id)

            step_handlers: dict[AuthStep, Callable[[str, AuthSession, str], Awaitable[AuthReply]]] = {
                AuthStep.NAME: self._receive_name,
                AuthStep.STUDENT_NUMBER: self._receive_student_number,
                AuthStep.GRADE: self._receive_grade,
                AuthStep.EMAIL: self._receive_email,
                AuthStep.CODE: self._receive_code,
            }
            return await step_handlers[session.step](user_id, session, text)

    # ------------------------------------------------------------------
    # 各段階の処理 (AuthStep ごとに 1 つ)
    # ------------------------------------------------------------------

    async def _receive_name(self, user_id: str, session: AuthSession, text: str) -> AuthReply:
        """
        [NAME] 氏名を受け取り、学籍番号を尋ねる
        """
        if not text:
            return AuthReply(["名前 (フルネーム) を教えてください。"])
        session.name = text
        session.step = AuthStep.STUDENT_NUMBER
        return AuthReply(["学籍番号を教えてください。"])

    async def _receive_student_number(self, user_id: str, session: AuthSession, text: str) -> AuthReply:
        """
        [STUDENT_NUMBER] 学籍番号を受け取り、学年を尋ねる
        """
        if not is_valid_student_number(text):
            return AuthReply(["学籍番号の形式が正しくありません。英数字 8 文字で入力してください。"])
        session.student_number = text
        session.step = AuthStep.GRADE
        return AuthReply([f"学年を以下から教えてください: {Grade.choices_text()}"])

    async def _receive_grade(self, user_id: str, session: AuthSession, text: str) -> AuthReply:
        """
        [GRADE] 学年を受け取り、メールアドレスを尋ねる
        """
        grade = Grade.parse(text)
        if grade is None:
            return AuthReply([f"学年の形式が正しくありません。以下から選んでください: {Grade.choices_text()}"])
        session.grade = grade
        session.step = AuthStep.EMAIL
        return AuthReply([f"大学のメールアドレス (@{self._allowed_email_domain}) を教えてください。"])

    async def _receive_email(self, user_id: str, session: AuthSession, text: str) -> AuthReply:
        """
        [EMAIL] メールアドレスを受け取り、登録情報と照合して、認証コードをメールで送る
        """
        if not is_valid_email(text, self._allowed_email_domain):
            return AuthReply(
                [f"メールアドレスの形式が正しくありません。@{self._allowed_email_domain} のアドレスを入力してください。"]
            )
        session.email = text

        student = self._student_controller.find_matching_student(
            session.name, session.student_number, session.grade, session.email
        )
        if student is None:
            logger.info("User %s entered information that does not match any student", user_id)
            return self._restart(user_id, "入力された情報が、登録されているメンバー情報と一致しませんでした。")
        if student.discord_id not in (None, user_id):
            self.cancel(user_id)
            return AuthReply(
                ["このメンバー情報はすでに別の Discord アカウントで認証されています。管理者に連絡してください。"]
            )

        code = self._generate_code()
        try:
            await self._mail_sender.send_verification_code(session.email, code, CODE_EXPIRE_MINUTES)
        except MailSendError:
            logger.exception("Failed to send verification code to user %s", user_id)
            return AuthReply(
                ["認証メールの送信に失敗しました。時間をおいて、もう一度メールアドレスを入力してください。"]
            )

        session.student_uuid = student.uuid
        session.code = code
        session.code_expires_at = self._now() + timedelta(minutes=CODE_EXPIRE_MINUTES)
        session.failed_code_attempts = 0
        session.step = AuthStep.CODE
        return AuthReply(
            [
                f"{session.email} に認証コードを送信しました。",
                f"メールに記載された 6 桁の認証コードを送信してください。(有効期限: {CODE_EXPIRE_MINUTES} 分)",
                "メールが届かない場合は「やり直し」と送信してください。",
            ]
        )

    async def _receive_code(self, user_id: str, session: AuthSession, text: str) -> AuthReply:
        """
        [CODE] 認証コードを受け取り、正しければ学生情報に Discord ID を紐付けて認証を完了する
        """
        if self._now() > session.code_expires_at:
            session.code = None
            session.step = AuthStep.EMAIL
            return AuthReply(["認証コードの有効期限が切れました。もう一度メールアドレスを入力してください。"])

        if not secrets.compare_digest(text, session.code):
            session.failed_code_attempts += 1
            remaining = MAX_CODE_ATTEMPTS - session.failed_code_attempts
            if remaining <= 0:
                return self._restart(user_id, f"認証コードを {MAX_CODE_ATTEMPTS} 回間違えました。")
            return AuthReply([f"認証コードが違います。(あと {remaining} 回入力できます)"])

        self.cancel(user_id)
        try:
            student = self._student_controller.link_discord_id(session.student_uuid, user_id)
        except StudentLinkError as error:
            return AuthReply([str(error)])

        logger.info("User %s authenticated as student %s", user_id, student.uuid)
        return AuthReply(["メール認証に成功しました！"], authenticated_student=student)

    def _restart(self, user_id: str, reason: str) -> AuthReply:
        """
        理由を伝えたうえで、手続きを最初からやり直す
        """
        reply = self.start(user_id)
        return AuthReply([reason, "最初からやり直してください。", "", reply.messages[-1]])
