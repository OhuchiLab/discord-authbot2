#!/usr/bin/env bash
# ソースコードの docstring から API ドキュメント (HTML) を docs/api/ に生成する
#   使い方: ./scripts/generate_api_docs.sh
#   閲覧:   docs/api/index.html をブラウザで開く
# ※ discord.Client から継承した属性の型注釈について pdoc が警告を出しますが、生成結果には影響しません。
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHONPATH=authbot/src python -m pdoc \
    --docformat google \
    --output-directory docs/api \
    main bot commands events controllers database external several_types utils
