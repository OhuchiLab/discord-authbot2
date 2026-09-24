"""
[単体] controllers.ImportController (CSV からの一括登録) のテスト

データベースは偽物 (InMemoryDatabase) に置き換えています。
StudentController は、副作用の無い業務ルールなので本物を使います。
"""

import pytest

from controllers import ImportController, StudentController, StudentImportError
from controllers.import_controller import MAX_ROWS
from several_types import Grade
from tests.fakes import InMemoryDatabase

HEADER = "氏名,学籍番号,学年,メールアドレス\n"


@pytest.fixture
def students() -> StudentController:
    return StudentController(InMemoryDatabase(), "shizuoka.ac.jp")


@pytest.fixture
def controller(students) -> ImportController:
    return ImportController(students)


# ----------------------------------------------------------------------
# CSV の読み取り (parse)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        (HEADER + "山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n").encode("utf-8"),
        (HEADER + "山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n").encode("utf-8-sig"),  # BOM 付き
        (HEADER + "山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\r\n").encode("cp932"),  # Excel (Shift_JIS)
    ],
    ids=["utf-8", "utf-8-bom", "shift_jis"],
)
def test_UTF8とShiftJISのCSVを読める(controller, data):
    plan = controller.parse(data)

    assert plan.errors == []
    assert [(row.line, row.student.name, row.student.grade) for row in plan.rows] == [(2, "山田 太郎", Grade.B4)]


def test_列の順番は問わず_余分な列と空の行は無視する(controller):
    data = (
        "メールアドレス,uuid,学年,氏名,学籍番号\n"
        "yamada@shizuoka.ac.jp,x,m1,山田 太郎,AB123456\n"
        ",,,,\n"
        "\n"
        "suzuki@shizuoka.ac.jp,y,OB/OG,鈴木 花子,CD123456\n"
    ).encode()

    plan = controller.parse(data)

    assert plan.errors == []
    assert [(row.line, row.student.name, row.student.grade) for row in plan.rows] == [
        (2, "山田 太郎", Grade.M1),
        (5, "鈴木 花子", Grade.OBOG),
    ]


def test_行ごとの問題を行番号付きで集める(controller, students):
    students.register_student("登録済み", "ZZ000001", Grade.M1, "zz@shizuoka.ac.jp")
    data = (
        HEADER
        + "山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n"
        + ",CD123456,B4,suzuki@shizuoka.ac.jp\n"  # 3 行目: 氏名が空
        + "佐藤 次郎,EF123456,B5,sato@shizuoka.ac.jp\n"  # 4 行目: 学年
        + "田中 三郎,ZZ000001,B4,tanaka@shizuoka.ac.jp\n"  # 5 行目: 登録済み
    ).encode()

    plan = controller.parse(data)

    assert plan.errors == [
        "3 行目: 氏名が空です。",
        "4 行目: 学年 「B5」 は使えません。B4, M1, M2, D1, D2, D3, TEACHER, OB/OG のいずれかにしてください。",
        "5 行目: 学籍番号 ZZ000001 はすでに登録されています。",
    ]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "CSV が空です。"),
        (HEADER.encode(), "CSV に登録する学生がいません。"),
        ("氏名,学籍番号\n".encode(), "CSV の 1 行目に、次の列がありません: 学年, メールアドレス"),
        (b"\x81\x7f", "CSV の文字コードを読み取れません。UTF-8 か Shift_JIS で保存してください。"),
    ],
    ids=["空", "見出しだけ", "列が足りない", "文字コード"],
)
def test_ファイル全体の問題はエラーにする(controller, data, message):
    with pytest.raises(StudentImportError, match=message):
        controller.parse(data)


def test_多すぎる行はエラーにする(controller):
    body = "".join(f"学生,AB{i:06d},B4,s{i}@shizuoka.ac.jp\n" for i in range(MAX_ROWS + 1))
    with pytest.raises(StudentImportError, match=f"{MAX_ROWS} 人まで"):
        controller.parse((HEADER + body).encode())


# ----------------------------------------------------------------------
# 登録 (commit)
# ----------------------------------------------------------------------


def test_問題が無ければ全員を登録する(controller, students):
    plan = controller.parse((HEADER + "山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n").encode())

    registered = controller.commit(plan)

    assert [s.name for s in registered] == ["山田 太郎"]
    assert students.find_by_student_number("AB123456") is not None


def test_問題がある計画は登録できない(controller, students):
    plan = controller.parse((HEADER + "山田 太郎,1234,B4,yamada@shizuoka.ac.jp\n").encode())
    with pytest.raises(StudentImportError):
        controller.commit(plan)
    assert students.list_students() == []


def test_確認中に重複が生じていたら何も登録しない(controller, students):
    plan = controller.parse((HEADER + "山田 太郎,AB123456,B4,yamada@shizuoka.ac.jp\n").encode())
    students.register_student("山田 太郎", "AB123456", Grade.B4, "other@shizuoka.ac.jp")

    with pytest.raises(StudentImportError, match="やり直してください"):
        controller.commit(plan)
    assert len(students.list_students()) == 1
