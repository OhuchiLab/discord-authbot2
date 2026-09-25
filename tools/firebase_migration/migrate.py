"""
移行ツールの本体: Firestore から読み込み → 変換 → 報告 → (--apply のときだけ) 学生情報ファイルに書き込む

    python -m tools.firebase_migration --credentials 鍵.json            # 確認だけ (何も書き込まない)
    python -m tools.firebase_migration --credentials 鍵.json --apply    # 書き込む
"""

import argparse
from pathlib import Path

from controllers import StudentController
from database import open_database

from .converter import MigrationPlan, convert
from .firebase_source import load_from_firebase

INDENT = "　"


def parse_args(args: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.firebase_migration",
        description="旧 Bot (Firebase) の学生情報を、新 Bot の学生情報ファイルに移します。既定では確認だけ行います。",
    )
    parser.add_argument("--credentials", required=True, help="Firebase のサービスアカウントの鍵 (JSON ファイル)")
    parser.add_argument("--database", default="data/students.msgpack", help="移行先の学生情報ファイル (既定: %(default)s)")
    parser.add_argument("--backup-dir", default="data/backups", help="書き込み後のバックアップの保存先 (既定: %(default)s)")
    parser.add_argument("--backup-keep", type=int, default=50, help="残すバックアップの数 (既定: %(default)s)")
    parser.add_argument("--email-domain", default="shizuoka.ac.jp", help="受け付けるメールアドレスのドメイン (既定: %(default)s)")
    parser.add_argument("--apply", action="store_true", help="付けると、学生情報ファイルに書き込む (付けなければ確認だけ)")
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """
    移行ツールを実行する

    Returns:
        int: 終了コード (0: 成功、1: 移行先にすでに学生情報がある)
    """
    options = parse_args(args)
    database = open_database(Path(options.database), Path(options.backup_dir), options.backup_keep)
    if database.get_all():
        print(f"移行先にすでに学生情報があります ({options.database})。空の状態で実行してください。")
        return 1

    members, verified_emails = load_from_firebase(options.credentials)
    plan = convert(members, verified_emails, StudentController(database, options.email_domain))
    print_report(len(members), plan)

    if not options.apply:
        print()
        print("確認だけ行い、何も書き込んでいません。内容に問題が無ければ --apply を付けて実行してください。")
        return 0

    database.add_many(plan.students)
    print()
    print(f"{len(plan.students)} 人を移しました (保存先: {options.database})。")
    return 0


def print_report(member_count: int, plan: MigrationPlan) -> None:
    """変換した結果を表示する"""
    authenticated = sum(1 for student in plan.students if student.discord_id is not None)
    print(f"Firestore の学生情報: {member_count} 件")
    print(f"移す人: {len(plan.students)} 人 (認証済み {authenticated} 人 / 未認証 {len(plan.students) - authenticated} 人)")
    print(f"飛ばす人: {len(plan.skipped)} 人")
    for line in plan.skipped:
        print(f"{INDENT}{line}")
    print(f"紐付けを外して移す人: {len(plan.notes)} 人")
    for line in plan.notes:
        print(f"{INDENT}{line}")
