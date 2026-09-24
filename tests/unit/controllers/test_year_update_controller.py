"""
[単体] controllers.YearUpdateController (現役メンバーの年度更新) のテスト

データベースと Discord は偽物に置き換えています。
"""

import dataclasses
from datetime import date

import pytest

from controllers import RoleController, YearUpdateController, YearUpdateError
from controllers.year_update_controller import DEFAULT_NEXT_GRADES, SELECTABLE_NEXT_GRADES
from several_types import AUTHORIZED_ROLE, GRADE_ROLES, Grade, StudentInfo
from tests.fakes import FakeDiscordGateway, InMemoryDatabase


def make_student(uuid: str, grade: Grade, discord_id: str | None = None) -> StudentInfo:
    return StudentInfo(uuid, f"学生 {uuid}", f"{uuid:0>8}", f"{uuid}@shizuoka.ac.jp", grade, discord_id)


@pytest.fixture
def discord() -> FakeDiscordGateway:
    return FakeDiscordGateway()


@pytest.fixture
def database() -> InMemoryDatabase:
    return InMemoryDatabase(
        [
            make_student("b4", Grade.B4, discord_id="101"),
            make_student("m2", Grade.M2),
            make_student("obog", Grade.OBOG),
            make_student("teacher", Grade.TEACHER),
        ]
    )


@pytest.fixture
def today() -> list[date]:
    """テストから変えられる「今日」"""
    return [date(2027, 3, 1)]


@pytest.fixture
def controller(database, discord, today) -> YearUpdateController:
    return YearUpdateController(database, RoleController(discord), today=lambda: today[0])


# ----------------------------------------------------------------------
# 年度
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("today_value", "expected"),
    [
        (date(2027, 3, 31), 2027),  # 2026年度の最終日 → 次は 2027年度
        (date(2027, 4, 1), 2028),  # 2027年度の初日 → 次は 2028年度
        (date(2026, 12, 31), 2027),
    ],
)
def test_既定の年度は今日が属する年度の次の年度(controller, today, today_value, expected):
    today[0] = today_value
    assert controller.default_fiscal_year() == expected


def test_年度を省略すると既定の年度で候補を作る(controller):
    assert controller.create_plan().fiscal_year == 2027


# ----------------------------------------------------------------------
# 更新候補の作成
# ----------------------------------------------------------------------


def test_既定の更新先は仕様どおり():
    assert DEFAULT_NEXT_GRADES == {
        Grade.B4: Grade.M1,
        Grade.M1: Grade.M2,
        Grade.M2: Grade.OBOG,
        Grade.D1: Grade.D2,
        Grade.D2: Grade.D3,
        Grade.D3: Grade.OBOG,
    }


def test_現役学生だけが既定の更新先付きで候補になる(controller):
    plan = controller.create_plan(2027)

    assert [(c.student_uuid, c.current_grade, c.next_grade) for c in plan.candidates] == [
        ("b4", Grade.B4, Grade.M1),
        ("m2", Grade.M2, Grade.OBOG),
    ]


def test_候補を作っただけでは何も変わらない(controller, database):
    controller.create_plan(2027)
    assert database.save_count == 0


def test_実行済みの年度は候補を作れない(controller, database):
    database.commit_year_update([], 2027)
    with pytest.raises(YearUpdateError, match="2027年度の現役更新は既に実行されています。"):
        controller.create_plan(2027)


def test_現役学生がいなければ候補を作れない(discord, today):
    controller = YearUpdateController(InMemoryDatabase(), RoleController(discord), today=lambda: today[0])
    with pytest.raises(YearUpdateError, match="対象となる現役メンバーがいません"):
        controller.create_plan(2027)


# ----------------------------------------------------------------------
# 更新先の変更
# ----------------------------------------------------------------------


def test_更新先を変更できる(controller):
    plan = controller.create_plan(2027)
    controller.change_next_grade(plan, "b4", Grade.B4)
    assert plan.find("b4").next_grade == Grade.B4
    assert plan.find("b4").is_changed


def test_教員には変更できない(controller):
    assert Grade.TEACHER not in SELECTABLE_NEXT_GRADES
    plan = controller.create_plan(2027)
    with pytest.raises(YearUpdateError):
        controller.change_next_grade(plan, "b4", Grade.TEACHER)


# ----------------------------------------------------------------------
# 確定
# ----------------------------------------------------------------------


async def test_確定すると学生情報と実行済み年度を保存し_ロールを同期する(controller, database, discord):
    discord.add_member("101", roles=(AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.B4].name))
    plan = controller.create_plan(2027)

    result = await controller.commit(plan)

    assert database.find_by_uuid("b4").grade == Grade.M1
    assert database.find_by_uuid("m2").grade == Grade.OBOG
    assert database.find_by_uuid("obog").grade == Grade.OBOG
    assert database.completed_fiscal_years() == {2027}
    assert discord.members["101"].roles == {AUTHORIZED_ROLE.name, GRADE_ROLES[Grade.M1].name}
    assert (result.updated_count, result.synced_count) == (2, 1)


async def test_サーバーにいない認証済み学生は結果で知らせる(controller, database):
    result = await controller.commit(controller.create_plan(2027))
    assert result.not_in_server == ["学生 b4"]
    assert database.find_by_uuid("b4").grade == Grade.M1


async def test_確定前に他の管理者が同じ年度を確定していたらエラー(controller, database):
    first = controller.create_plan(2027)
    second = controller.create_plan(2027)
    await controller.commit(first)

    with pytest.raises(YearUpdateError, match="既に実行されています"):
        await controller.commit(second)


async def test_候補を作った後に学生情報が変わっていたらエラーで何も保存しない(controller, database):
    plan = controller.create_plan(2027)
    database.update(dataclasses.replace(database.find_by_uuid("b4"), grade=Grade.M1))

    with pytest.raises(YearUpdateError, match="やり直してください"):
        await controller.commit(plan)
    assert database.completed_fiscal_years() == set()


async def test_候補を作った後に現役学生が追加されていたらエラー(controller, database):
    plan = controller.create_plan(2027)
    database.add(make_student("new", Grade.B4))

    with pytest.raises(YearUpdateError, match="やり直してください"):
        await controller.commit(plan)
