"""
[単体] controllers.AuthFlowController (DM での認証手続き) のテスト

データベース・メール送信・時計は偽物に置き換えています。
StudentController は副作用の無い業務ルールなので本物を使います。
"""


import pytest

from controllers import AuthFlowController, StudentController
from controllers.auth_flow_controller import CODE_EXPIRE_MINUTES, MAX_CODE_ATTEMPTS
from several_types import Grade
from tests.fakes import FakeClock, FakeMailSender, InMemoryDatabase

USER_ID = "111"
CODE = "123456"


@pytest.fixture
def students() -> StudentController:
    controller = StudentController(InMemoryDatabase(), "shizuoka.ac.jp")
    controller.register_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    return controller


@pytest.fixture
def mail() -> FakeMailSender:
    return FakeMailSender()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def flow(students, mail, clock) -> AuthFlowController:
    return AuthFlowController(students, mail, "shizuoka.ac.jp", now=clock.now, code_generator=lambda: CODE)


async def send(flow: AuthFlowController, text: str):
    return await flow.handle_message(USER_ID, text)


async def answer_until_code(flow: AuthFlowController):
    flow.start(USER_ID)
    await send(flow, "山田 太郎")
    await send(flow, "AB123456")
    await send(flow, "m1")
    return await send(flow, "yamada@shizuoka.ac.jp")


async def test_正しく答えると認証が完了し_DiscordIDが保存される(flow, students, mail):
    reply = await answer_until_code(flow)
    assert "認証コードを送信しました" in reply.text
    assert [(m.to_address, m.code) for m in mail.sent] == [("yamada@shizuoka.ac.jp", CODE)]

    reply = await send(flow, CODE)
    assert reply.authenticated_student is not None
    assert reply.authenticated_student.discord_id == USER_ID
    assert students.find_by_discord_id(USER_ID) is not None


async def test_手続き中でないユーザーからDMが来たら手続きを始める(flow):
    reply = await send(flow, "こんにちは")
    assert "名前 (フルネーム) を教えてください。" in reply.text


async def test_認証済みのユーザーからDMが来たらその旨を返す(flow):
    await answer_until_code(flow)
    await send(flow, CODE)
    reply = await send(flow, "こんにちは")
    assert reply.text == "すでに認証済みです。"


async def test_形式が不正な入力は同じ質問を繰り返す(flow):
    flow.start(USER_ID)
    await send(flow, "山田 太郎")
    assert "学籍番号の形式が正しくありません" in (await send(flow, "1234")).text
    await send(flow, "AB123456")
    assert "学年の形式が正しくありません" in (await send(flow, "B5")).text
    await send(flow, "M1")
    assert "メールアドレスの形式が正しくありません" in (await send(flow, "yamada@gmail.com")).text


async def test_登録情報と一致しなければ最初からやり直し(flow, mail):
    flow.start(USER_ID)
    await send(flow, "山田 次郎")
    await send(flow, "AB123456")
    await send(flow, "M1")
    reply = await send(flow, "yamada@shizuoka.ac.jp")
    assert "一致しませんでした" in reply.text
    assert mail.sent == []
    assert "学籍番号を教えてください。" in (await send(flow, "山田 太郎")).text


async def test_やり直しと送ると最初からやり直せる(flow):
    flow.start(USER_ID)
    await send(flow, "山田 太郎")
    reply = await send(flow, "やり直し")
    assert "名前 (フルネーム) を教えてください。" in reply.text


async def test_認証コードを間違え続けると最初からやり直し(flow):
    await answer_until_code(flow)
    for _ in range(MAX_CODE_ATTEMPTS - 1):
        assert "認証コードが違います" in (await send(flow, "000000")).text
    reply = await send(flow, "000000")
    assert "最初からやり直してください" in reply.text
    assert (await send(flow, CODE)).authenticated_student is None


async def test_有効期限切れの認証コードは受け付けない(flow, clock):
    await answer_until_code(flow)
    clock.advance(minutes=CODE_EXPIRE_MINUTES, seconds=1)
    reply = await send(flow, CODE)
    assert "有効期限が切れました" in reply.text
    assert reply.authenticated_student is None


async def test_全角数字の認証コードも受け付ける(flow):
    await answer_until_code(flow)
    assert (await send(flow, "１２３４５６")).authenticated_student is not None


async def test_メール送信に失敗したらメールアドレスを入力し直せる(flow, mail):
    flow.start(USER_ID)
    await send(flow, "山田 太郎")
    await send(flow, "AB123456")
    await send(flow, "M1")
    mail.fail = True
    assert "送信に失敗しました" in (await send(flow, "yamada@shizuoka.ac.jp")).text
    mail.fail = False
    assert "認証コードを送信しました" in (await send(flow, "yamada@shizuoka.ac.jp")).text


async def test_別のアカウントで認証済みの学生情報では認証できない(flow, students, mail):
    student = students.find_matching_student("山田 太郎", "AB123456", Grade.M1, "yamada@shizuoka.ac.jp")
    students.link_discord_id(student.uuid, "999")
    reply = await answer_until_code(flow)
    assert "別の Discord アカウント" in reply.text
    assert mail.sent == []
