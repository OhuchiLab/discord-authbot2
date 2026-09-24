"""
他パッケージで使用する様々な便利関数を定義するパッケージ。

| モジュール | 内容 |
| --- | --- |
| `config` | .env / 環境変数からの設定値の読み込み (`load_config`) |
| `validators` | 入力値の形式チェックと比較用の正規化 |
"""

from .config import BotConfig, ConfigError, load_config
from .validators import (
    is_valid_email,
    is_valid_student_number,
    normalize_email,
    normalize_input,
    normalize_name,
    normalize_student_number,
)
