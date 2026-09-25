"""
旧 Bot の Firestore と Firebase Auth から、移行に必要なデータを読み込む

firebase-admin が必要です (移行のときだけ使うため、Bot 本体の requirements.txt には入れていません)。

    pip install -r requirements-migration.txt

Firebase への接続には、旧 Bot と同じサービスアカウントの鍵 (JSON ファイル) を使います。
(Firebase コンソール > プロジェクトの設定 > サービス アカウント > 新しい秘密鍵を生成)
"""

from pathlib import Path

from utils import normalize_email

from .converter import FirebaseMember

MEMBERS_COLLECTION = "members"
"""旧 Bot が学生情報を保存していた Firestore のコレクション名"""


def load_from_firebase(credentials_path: str) -> tuple[list[FirebaseMember], set[str]]:
    """
    Firestore の学生情報と、Firebase Auth でメール認証が済んでいるメールアドレスを読み込む (読み込むだけで変更はしない)

    Args:
        credentials_path (str): サービスアカウントの鍵 (JSON ファイル) のパス

    Returns:
        tuple: (Firestore の members コレクションのドキュメント, メール認証済みのメールアドレス (小文字))

    Raises:
        SystemExit: firebase-admin が無い、または鍵のファイルが無い場合 (理由を表示して終了する)
    """
    try:
        import firebase_admin
        from firebase_admin import auth, credentials, firestore
    except ImportError as error:
        raise SystemExit("firebase-admin がありません。pip install -r requirements-migration.txt を実行してください。") from error
    if not Path(credentials_path).is_file():
        raise SystemExit(f"サービスアカウントの鍵が見つかりません: {credentials_path}")

    app = firebase_admin.initialize_app(credentials.Certificate(credentials_path), name="authbot-migration")
    try:
        members = []
        for document in firestore.client(app).collection(MEMBERS_COLLECTION).stream():
            data = document.to_dict() or {}
            members.append(
                FirebaseMember(
                    doc_id=document.id,
                    name=data.get("name"),
                    student_number=data.get("student_number"),
                    grade=data.get("grade"),
                    mail=data.get("mail"),
                    discord_id=data.get("discordId"),
                )
            )
        verified_emails = {
            normalize_email(user.email)
            for user in auth.list_users(app=app).iterate_all()
            if user.email and user.email_verified
        }
    finally:
        firebase_admin.delete_app(app)
    return members, verified_emails
