"""
`python -m tools.firebase_migration` の入口 (プロジェクトのフォルダで実行する)

新 Bot の部品 (authbot/src/ 以下) を使うため、authbot/src/ をインポート先に追加してから実行します。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "authbot" / "src"))

from tools.firebase_migration.migrate import main  # noqa: E402  (sys.path を設定した後にインポートする必要がある)

sys.exit(main())
