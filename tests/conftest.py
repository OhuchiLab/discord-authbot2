"""
すべてのテストに共通する設定

tests/<階層名>/ 以下のテストに、階層名のマーカー (unit / api / functional / system) を自動で付けます。
これにより `pytest -m unit` のように階層を指定して実行できます。
"""

from pathlib import Path

import pytest

TEST_LEVELS = ("unit", "api", "functional", "system")
TESTS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        level = item.path.relative_to(TESTS_DIR).parts[0]
        if level in TEST_LEVELS:
            item.add_marker(level)
