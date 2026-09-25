"""
旧 Bot (discord-authbot、Firebase で管理) の学生情報を、新 Bot の学生情報ファイルに移す移行ツール

| モジュール | 内容 |
| --- | --- |
| `converter` | Firestore のデータ → 新 Bot の学生情報 への変換 (Firebase には接続しない) |
| `firebase_source` | Firestore と Firebase Auth からの読み込み (firebase-admin を使う) |
| `migrate` | コマンドラインから実行する入口 (`python -m tools.firebase_migration`) |

手順は docs/migration_from_firebase.md を参照してください。
"""
