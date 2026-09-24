"""
`python -m authbot` で Bot を起動するための入口

ソースコードは authbot/src/ 以下にあり、各パッケージは
`import database` のように authbot/src/ を基準にインポートし合います。
そのため、ここで authbot/src/ をインポート先に追加してから main() を呼びます。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from main import main  # noqa: E402  (sys.path を設定した後にインポートする必要がある)

main()
