"""
Discord で使用するスラッシュコマンドを定義・実装するパッケージ。

1 コマンドにつき 1 モジュールです。
新しいコマンドを追加したら、`setup_all_commands()` に登録処理を追加してください。

| モジュール | コマンド | 実行できる人 | 内容 |
| --- | --- | --- | --- |
| `health_check` | /health_check | 全員 | Bot が動いているか確認する |
| `register` | /register | 管理者 | メンバーの学生情報を登録する |
| `auth` | /auth | 全員 | DM での認証手続きを (再) 開始する |
| `list_students` | /list_students | 管理者 | 学生情報の一覧を表示する (表示とページ切り替えは `list_students_view`) |
| `delete_student` | /delete_student | 管理者 | 特定の学生情報を削除する (確認画面は `delete_student_view`) |
| `export_students` | /export_students | 管理者 | 学生情報を CSV / msgpack のファイルに書き出す |
| `edit_student` | /edit_student | 管理者 | 特定の学生情報を変更する (確認画面は `edit_student_view`) |
| `update_grades` | /update_grades | 管理者 | 年度の切り替えに合わせて現役メンバーの学年を更新する (確認画面は `update_grades_view`) |

`grade_option` は、学年オプションの選択肢 (表示名付き) の定義です。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from .auth import setup_auth_command
from .delete_student import setup_delete_student_command
from .edit_student import setup_edit_student_command
from .export_students import setup_export_students_command
from .health_check import setup_health_check_command
from .list_students import setup_list_students_command
from .register import setup_register_command
from .update_grades import setup_update_grades_command

if TYPE_CHECKING:
    from bot import AuthBot

logger = logging.getLogger(__name__)


def setup_all_commands(bot: AuthBot) -> None:
    """
    すべてのスラッシュコマンドと、共通のエラー処理を Bot に登録する

    Args:
        bot (AuthBot): Bot 本体
    """
    setup_health_check_command(bot)
    setup_register_command(bot)
    setup_auth_command(bot)
    setup_update_grades_command(bot)
    setup_edit_student_command(bot)
    setup_list_students_command(bot)
    setup_delete_student_command(bot)
    setup_export_students_command(bot)

    @bot.tree.error
    async def on_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        # コマンドの処理中に想定外のエラーが起きた場合は、ログに残してユーザーに知らせる
        logger.exception("Error while executing /%s", interaction.command.name if interaction.command else "?", exc_info=error)
        message = "コマンドの実行中にエラーが発生しました。"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
