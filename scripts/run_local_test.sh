#!/usr/bin/env bash
# =============================================================================
# Bot を手元でテスト起動する
#
#   使い方:  ./scripts/run_local_test.sh      (Ctrl+C で終了)
#
#   - 設定は .env ではなく .env.system を使います (本番の設定・学生情報には触れません)
#   - 認証メールは実際には送らず、テスト用のメールサーバーが画面に表示します
#   - 学生情報は data/system-test/ に保存されます
# =============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env.system"
PYTHON="${PROJECT_DIR}/.venv/bin/python"
MAIL_PORT=1025

cd "${PROJECT_DIR}"

# ---- 設定ファイルの確認 -------------------------------------------------------
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "エラー: .env.system がありません。docs/test_design.md の 7.1 を参考に作成してください。" >&2
    exit 1
fi
for name in DISCORD_TOKEN GUILD_ID; do
    if ! grep -qE "^${name}=.+" "${ENV_FILE}"; then
        echo "エラー: .env.system の ${name} が空です。値を設定してください。" >&2
        exit 1
    fi
done

# ---- テスト用メールサーバーを起動し、終了時に止める -----------------------------
"${PYTHON}" scripts/local_mail_server.py "${MAIL_PORT}" &
MAIL_SERVER_PID=$!
trap 'kill "${MAIL_SERVER_PID}" 2>/dev/null || true' EXIT
sleep 1

# ---- Bot を起動 ---------------------------------------------------------------
echo "Bot を起動します (Ctrl+C で終了)"
AUTHBOT_ENV_FILE="${ENV_FILE}" "${PYTHON}" -m authbot
