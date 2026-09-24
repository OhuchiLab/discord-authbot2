"""
[API] テスト用の偽物 (tests/fakes) が、本物と同じ公開 I/F を持っていることのテスト

本物のメソッドを変更したのに偽物を直し忘れると、偽物を使うテストだけが通ってしまいます。
それを防ぐため、公開メソッドの名前・引数・async かどうかが一致していることを確認します。
"""

import inspect

import pytest

from database import DatabaseController
from external import DiscordGateway, MailSender
from tests.fakes import FakeDiscordGateway, FakeMailSender, InMemoryDatabase

PAIRS = [
    (DiscordGateway, FakeDiscordGateway),
    (MailSender, FakeMailSender),
    (DatabaseController, InMemoryDatabase),
]


def public_methods(cls: type) -> dict[str, object]:
    return {
        name: member
        for name, member in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_")
    }


@pytest.mark.parametrize(("real", "fake"), PAIRS, ids=lambda cls: cls.__name__)
def test_偽物は本物の公開メソッドをすべて同じ形で持つ(real, fake):
    fake_methods = public_methods(fake)
    for name, real_method in public_methods(real).items():
        assert name in fake_methods, f"{fake.__name__} に {name} がありません"
        fake_method = fake_methods[name]
        assert inspect.signature(fake_method).parameters.keys() == inspect.signature(real_method).parameters.keys(), (
            f"{fake.__name__}.{name} の引数が本物と違います"
        )
        assert inspect.iscoroutinefunction(fake_method) == inspect.iscoroutinefunction(real_method), (
            f"{fake.__name__}.{name} の async の有無が本物と違います"
        )
