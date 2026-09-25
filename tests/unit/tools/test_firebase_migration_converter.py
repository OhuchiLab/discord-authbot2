"""
[単体] tools.firebase_migration.converter (旧 Bot の Firestore のデータ → 新 Bot の学生情報) のテスト
"""

import pytest

from controllers import StudentController
from several_types import Grade, StudentInfo
from tests.fakes import InMemoryDatabase
from tools.firebase_migration.converter import FirebaseMember, convert


@pytest.fixture
def students() -> StudentController:
    """移行先 (空) の学生情報に対する入力チェック"""
    return StudentController(InMemoryDatabase(), "shizuoka.ac.jp")


def member(doc_id: str, **fields) -> FirebaseMember:
    values = {
        "name": "山田 太郎",
        "student_number": "AB123456",
        "grade": "B4",
        "mail": "yamada@shizuoka.ac.jp",
        "discord_id": None,
    }
    values.update(fields)
    return FirebaseMember(doc_id=doc_id, **values)


def test_メール認証済みの人は紐付けごと移し_ドキュメントIDをuuidにする(students):
    plan = convert([member("doc-1", discord_id="101")], {"yamada@shizuoka.ac.jp"}, students)

    assert plan.students == [
        StudentInfo("doc-1", "山田 太郎", "AB123456", "yamada@shizuoka.ac.jp", Grade.B4, "101")
    ]
    assert plan.skipped == [] and plan.notes == []


def test_メール認証が済んでいない人は未認証として移す(students):
    plan = convert([member("doc-1", discord_id="101")], set(), students)

    assert plan.students[0].discord_id is None
    assert plan.notes == ["doc-1 山田 太郎: メール認証が済んでいないため、未認証として移します (Discord ID 101)"]


def test_discordIdが無い人は未認証として移す(students):
    plan = convert([member("doc-1")], {"yamada@shizuoka.ac.jp"}, students)
    assert plan.students[0].discord_id is None
    assert plan.notes == []


def test_表記ゆれは新Botの形にそろえる(students):
    plan = convert(
        [member("doc-1", student_number="ab123456", grade="m1", mail="Yamada@Shizuoka.ac.jp", discord_id="101")],
        {"yamada@shizuoka.ac.jp"},
        students,
    )
    student = plan.students[0]
    assert (student.student_number, student.grade, student.email, student.discord_id) == (
        "AB123456",
        Grade.M1,
        "yamada@shizuoka.ac.jp",
        "101",
    )


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"name": None}, "氏名 がありません"),
        ({"mail": None}, "メールアドレス がありません"),
        ({"grade": "B5"}, "学年 「B5」 は使えません"),
        ({"student_number": "1234"}, "学籍番号は英数字 8 文字"),
        ({"mail": "yamada@gmail.com"}, "@shizuoka.ac.jp"),
    ],
)
def test_形式が不正な人は理由付きで飛ばす(students, fields, reason):
    plan = convert([member("doc-1", **fields)], set(), students)

    assert plan.students == []
    assert len(plan.skipped) == 1
    assert plan.skipped[0].startswith("doc-1 ")
    assert reason in plan.skipped[0]


def test_学籍番号やメールアドレスが重複していたら後の人を飛ばす(students):
    plan = convert(
        [
            member("doc-1"),
            member("doc-2", name="山田 花子", mail="hanako@shizuoka.ac.jp"),  # 学籍番号が doc-1 と同じ
            member("doc-3", name="鈴木 次郎", student_number="CD123456"),  # メールが doc-1 と同じ
        ],
        set(),
        students,
    )

    assert [s.uuid for s in plan.students] == ["doc-1"]
    assert [line.split(" ")[0] for line in plan.skipped] == ["doc-2", "doc-3"]
    assert all("重複" in line for line in plan.skipped)


def test_DiscordIDが重複していたら後の人は紐付けを外して移す(students):
    plan = convert(
        [
            member("doc-1", discord_id="101"),
            member("doc-2", name="鈴木 花子", student_number="CD123456", mail="suzuki@shizuoka.ac.jp", discord_id="101"),
        ],
        {"yamada@shizuoka.ac.jp", "suzuki@shizuoka.ac.jp"},
        students,
    )

    assert [(s.uuid, s.discord_id) for s in plan.students] == [("doc-1", "101"), ("doc-2", None)]
    assert "doc-2" in plan.notes[0] and "Discord ID 101" in plan.notes[0] and "重複" in plan.notes[0]


def test_数値で保存された学籍番号も文字列として読む(students):
    plan = convert([member("doc-1", student_number=71234567)], set(), students)
    assert plan.students[0].student_number == "71234567"
