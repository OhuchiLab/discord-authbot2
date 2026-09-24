#!/usr/bin/env bash
# =============================================================================
# install_service.sh で登録した、認証 Bot の自動起動を解除する
#
#   使い方:  ./scripts/uninstall_service.sh
#
#   Bot を止めて、OS の起動時に立ち上がらないようにします。
#   学生情報 (data/) や .env は削除しません。
# =============================================================================
set -euo pipefail

SERVICE_NAME="authbot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ ! -f "${SERVICE_FILE}" ]]; then
    echo "サービス ${SERVICE_NAME} は登録されていません。"
    exit 0
fi

echo "サービスを停止して登録を解除します (管理者のパスワードを求められることがあります)..."
sudo systemctl disable --now "${SERVICE_NAME}"
sudo rm "${SERVICE_FILE}"
sudo systemctl daemon-reload

echo "登録を解除しました。"
