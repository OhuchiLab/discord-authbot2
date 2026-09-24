#!/usr/bin/env bash
# =============================================================================
# 認証 Bot を、OS の起動時に自動で立ち上がるように登録する (Linux Mint / Ubuntu 向け)
#
#   使い方:  ./scripts/install_service.sh            登録して、すぐに起動する
#            ./scripts/install_service.sh --print    登録内容 (サービス定義) を表示するだけ
#
#   登録後の操作:
#            sudo systemctl status authbot      状態を見る
#            sudo systemctl restart authbot     再起動する (コードや .env を変更したとき)
#            sudo systemctl stop authbot        止める
#            journalctl -u authbot -f           ログを見る (Ctrl+C で終了)
#            ./scripts/uninstall_service.sh     登録を解除する
#
#   仕組み:
#     systemd (Linux Mint で OS の起動時にプログラムを立ち上げる仕組み) に
#     「authbot」というサービスを登録します。
#     - Bot は、このスクリプトを実行したユーザーの権限で動きます (root では動かしません)
#     - ネットワークにつながってから起動します
#     - Bot が異常終了したら 10 秒後に自動で再起動します
#     - ログは journalctl で見られます
# =============================================================================
set -euo pipefail

SERVICE_NAME="authbot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# このスクリプトは scripts/ にあるので、1 つ上がプロジェクトのフォルダ
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"

# sudo で実行された場合も、元のユーザーで Bot を動かす
RUN_USER="${SUDO_USER:-$(id -un)}"
RUN_GROUP="$(id -gn "${RUN_USER}")"

# -----------------------------------------------------------------------------
# サービス定義 (systemd の unit ファイル) を出力する
# -----------------------------------------------------------------------------
print_service_definition() {
    cat <<EOF
[Unit]
Description=Ohuchi Lab Discord authentication bot (discord-authbot2)
# ネットワークにつながってから起動する
Wants=network-online.target
After=network-online.target
# 設定ミスなどで起動直後の失敗を繰り返す場合は、5 分間に 5 回で再起動をあきらめる
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
# .env と data/ はこのフォルダを基準に読み書きされる
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} -m authbot
# ログをすぐに journalctl に出す
Environment=PYTHONUNBUFFERED=1
# 異常終了したら 10 秒後に再起動する
Restart=on-failure
RestartSec=10
# 安全のための制限 (/usr や /etc などを書き換えられないようにする)
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
# OS の起動時 (通常の起動状態になったとき) に立ち上げる
WantedBy=multi-user.target
EOF
}

# -----------------------------------------------------------------------------
# 事前チェック: 起動に必要なものが揃っているか
# -----------------------------------------------------------------------------
check_requirements() {
    if [[ "${RUN_USER}" == "root" ]]; then
        echo "エラー: root ユーザーでは登録できません。普段使っているユーザーで実行してください (sudo は自動で求められます)。" >&2
        exit 1
    fi

    if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
        echo "エラー: ${PROJECT_DIR}/.env がありません。" >&2
        echo "       .env.example をコピーして .env を作り、トークンなどを設定してください。" >&2
        exit 1
    fi

    if [[ ! -x "${VENV_PYTHON}" ]]; then
        echo "Python の仮想環境 (.venv) が無いため作成します..."
        python3 -m venv "${PROJECT_DIR}/.venv"
    fi
    echo "必要なライブラリをインストールします..."
    "${VENV_PYTHON}" -m pip install --quiet -r "${PROJECT_DIR}/requirements.txt"
}

# -----------------------------------------------------------------------------
# メイン処理
# -----------------------------------------------------------------------------
if [[ "${1:-}" == "--print" ]]; then
    print_service_definition
    exit 0
fi

check_requirements

echo "サービスを登録します (管理者のパスワードを求められることがあります)..."
print_service_definition | sudo tee "${SERVICE_FILE}" > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"

echo
echo "登録しました。次回から OS の起動時に自動で立ち上がります。"
echo "  状態を見る: sudo systemctl status ${SERVICE_NAME}"
echo "  ログを見る: journalctl -u ${SERVICE_NAME} -f"
echo
sudo systemctl --no-pager status "${SERVICE_NAME}" || true
