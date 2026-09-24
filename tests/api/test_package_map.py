"""
[API] パッケージ間の依存が、パッケージマップ (docs/images/package_map.png) どおりであることのテスト

authbot/src/ 以下のすべての .py ファイルの import 文を読み取り、
許可されていないパッケージへの依存が無いことを確認します。
パッケージマップを変更したら、下の ALLOWED_DEPENDENCIES も合わせて変更してください。
"""

import ast
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "authbot" / "src"

ALLOWED_DEPENDENCIES: dict[str, set[str]] = {
    # 起動・組み立て
    "main": {"bot", "controllers", "database", "external", "several_types", "utils"},
    "bot": {"commands", "events", "controllers", "several_types", "utils"},
    # Discord からの入口
    "commands": {"controllers", "several_types", "utils"},
    "events": {"controllers", "several_types", "utils"},
    # 業務ロジック
    "controllers": {"database", "external", "several_types", "utils"},
    # データの保存・外部機能
    "database": {"several_types", "utils"},
    "external": {"several_types", "utils"},
    # 様々なパッケージから使われるパッケージ
    "several_types": set(),
    "utils": {"several_types"},
}
"""各パッケージ (またはモジュール) が import してよい、プロジェクト内のパッケージ"""

DISCORD_ALLOWED = {"bot", "commands", "events", "external"}
"""discord.py を import してよいパッケージ。controllers 以下は Discord に依存しない"""

TYPE_ONLY_ALLOWED = {"commands": {"bot"}, "events": {"bot"}}
"""型注釈のためだけに (if TYPE_CHECKING: の中で) import してよいパッケージ"""


def find_imports(path: Path) -> list[tuple[str, bool]]:
    """
    ファイル中の絶対 import を (トップレベルのパッケージ名, TYPE_CHECKING の中かどうか) の一覧で返す
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    type_checking_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            type_checking_nodes |= {id(child) for child in ast.walk(node)}

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        imports += [(name.split(".")[0], id(node) in type_checking_nodes) for name in names]
    return imports


def source_files() -> list[tuple[str, Path]]:
    """(所属するパッケージ名, ファイル) の一覧"""
    return [(path.relative_to(SRC_DIR).parts[0].removesuffix(".py"), path) for path in sorted(SRC_DIR.rglob("*.py"))]


@pytest.mark.parametrize(("package", "path"), source_files(), ids=lambda value: str(value))
def test_パッケージマップにない依存が無い(package, path):
    assert package in ALLOWED_DEPENDENCIES, f"パッケージマップに無いパッケージです: {package}"

    violations = []
    for imported, type_only in find_imports(path):
        if imported == package:
            continue
        if imported == "discord" and package not in DISCORD_ALLOWED:
            violations.append("discord (Discord の操作は external.DiscordGateway を通すこと)")
        elif imported in ALLOWED_DEPENDENCIES and imported not in ALLOWED_DEPENDENCIES[package]:
            if not (type_only and imported in TYPE_ONLY_ALLOWED.get(package, set())):
                violations.append(imported)

    assert violations == [], f"{path.relative_to(SRC_DIR)} が許可されていない依存を持っています: {violations}"
