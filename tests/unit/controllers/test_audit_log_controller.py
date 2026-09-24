"""
[単体] controllers.AuditLogController (変更履歴のログ用チャンネルへの投稿) のテスト

Discord は偽物 (FakeDiscordGateway) に置き換えています。
"""

import dataclasses

import pytest

from controllers import AuditLogController
from controllers.audit_log_controller import MAX_MESSAGE_LENGTH
from several_types import (
    ExportedFile,
    Grade,
    StudentDeleteResult,
    StudentEdit,
    StudentEditResult,
    StudentInfo,
    YearUpdateCandidate,
    YearUpdatePlan,
    YearUpdateResult,
)
from tests.fakes import FakeDiscordGateway

CHANNEL = "authbot-logs"
ADMIN_ID = "1"
YAMADA = StudentInfo("uuid-1", "山田 太郎", "AB123456", "yamada@shizuoka.ac.jp", Grade.B4, "101")


@pytest.fixture
def discord() -> FakeDiscordGateway:
    gateway = FakeDiscordGateway()
    gateway.add_channel(CHANNEL)
    return gateway


@pytest.fixture
def audit(discord) -> AuditLogController:
    return AuditLogController(discord, CHANNEL)


def last_log(discord) -> str:
    return discord.channels[CHANNEL][-1]


async def test_登録(audit, discord):
    await audit.student_registered(ADMIN_ID, YAMADA)
    assert last_log(discord) == "📝 学生情報の登録: <@1> が 山田 太郎 (AB123456) を登録しました (学年: B4)"


async def test_一括登録(audit, discord):
    suzuki = StudentInfo("uuid-2", "鈴木 花子", "CD123456", "suzuki@shizuoka.ac.jp", Grade.M1)
    await audit.students_imported(ADMIN_ID, [YAMADA, suzuki])
    assert last_log(discord).splitlines() == [
        "📝 学生情報の一括登録: <@1> が 2 人を登録しました",
        "　山田 太郎 (AB123456) B4",
        "　鈴木 花子 (CD123456) M1",
    ]


async def test_変更(audit, discord):
    after = dataclasses.replace(YAMADA, grade=Grade.M1, discord_id=None)
    edit = StudentEdit(before=YAMADA, after=after)
    await audit.student_edited(ADMIN_ID, edit, StudentEditResult(after, True, False, []))
    assert last_log(discord).splitlines() == [
        "✏️ 学生情報の変更: <@1> が 山田 太郎 (AB123456) を変更しました",
        "　学年: B4 → M1",
        "　Discord との紐付け: <@101> → なし (未認証)",
    ]


async def test_削除(audit, discord):
    await audit.student_deleted(ADMIN_ID, StudentDeleteResult(YAMADA, True, False, []))
    assert last_log(discord).splitlines() == [
        "🗑️ 学生情報の削除: <@1> が 山田 太郎 (AB123456) を削除しました",
        "　Discord: <@101> (未認証に戻しました)",
    ]


async def test_年度更新(audit, discord):
    plan = YearUpdatePlan(
        2027,
        [
            YearUpdateCandidate("uuid-1", "山田 太郎", "AB123456", "101", Grade.B4, Grade.M1, Grade.B4),
            YearUpdateCandidate("uuid-2", "鈴木 花子", "CD123456", None, Grade.M2, Grade.OBOG, Grade.OBOG),
        ],
    )
    await audit.grades_updated(ADMIN_ID, plan, YearUpdateResult(2027, 2, 1, [], []))
    assert last_log(discord).splitlines() == [
        "🎓 2027年度の現役更新: <@1> が 2 人の学年を更新しました",
        "　山田 太郎 (AB123456): B4 → B4 (留年) ✏️",
        "　鈴木 花子 (CD123456): M2 → OB/OG (卒業・修了)",
    ]


async def test_書き出し(audit, discord):
    await audit.students_exported(ADMIN_ID, ExportedFile("students-20270301.csv", b"", 3), "CSV")
    assert last_log(discord) == "📤 学生情報の書き出し: <@1> が 3 人分を CSV で書き出しました (students-20270301.csv)"


async def test_認証完了(audit, discord):
    await audit.member_authenticated(YAMADA)
    assert last_log(discord) == "✅ 認証: <@101> が 山田 太郎 (AB123456) として認証されました (学年: B4)"


async def test_Botの起動(audit, discord):
    await audit.bot_started()
    assert last_log(discord) == "🟢 Bot を起動しました。"


async def test_長いログは上限の長さごとに分けて投稿する(audit, discord):
    students = [
        StudentInfo(f"uuid-{i}", f"とても長い名前の学生{i:03d}", f"AB{i:06d}", f"s{i}@shizuoka.ac.jp", Grade.B4)
        for i in range(200)
    ]

    await audit.students_imported(ADMIN_ID, students)

    messages = discord.channels[CHANNEL]
    assert len(messages) > 1
    assert all(len(message) <= MAX_MESSAGE_LENGTH for message in messages)
    assert "\n".join(messages).count("とても長い名前の学生") == 200  # 1 人も欠けない


async def test_チャンネルが無くても権限が無くてもエラーにしない(discord):
    await AuditLogController(discord, "no-such-channel").bot_started()
    discord.can_post_to_channels = False
    await AuditLogController(discord, CHANNEL).bot_started()
    discord.bot_in_guild = False
    await AuditLogController(discord, CHANNEL).bot_started()


async def test_チャンネル名が無ければ何も投稿しない(discord):
    await AuditLogController(discord, None).bot_started()
    assert discord.channels[CHANNEL] == []
