"""
スラッシュコマンドの「学年」オプション

Discord の選択肢に、わかりやすい表示名 (例: 「OB/OG (卒業・修了)」) を付けます。
コマンドの処理には `Grade` として渡されます。

    使い方:  grade: GradeOption
"""

import discord
from discord import app_commands

from several_types import Grade

GRADE_LABELS: dict[Grade, str] = {
    Grade.B4: "B4",
    Grade.M1: "M1",
    Grade.M2: "M2",
    Grade.D1: "D1",
    Grade.D2: "D2",
    Grade.D3: "D3",
    Grade.TEACHER: "教員 (TEACHER)",
    Grade.OBOG: "OB/OG (卒業・修了)",
}
"""Discord の選択肢に表示する名前"""


class GradeTransformer(app_commands.Transformer):
    """Discord で選ばれた学年 (文字列) を Grade に変換する"""

    @property
    def type(self) -> discord.AppCommandOptionType:
        return discord.AppCommandOptionType.string

    @property
    def choices(self) -> list[app_commands.Choice[str]]:
        return [app_commands.Choice(name=label, value=grade.value) for grade, label in GRADE_LABELS.items()]

    async def transform(self, interaction: discord.Interaction, value: str) -> Grade:
        return Grade(value)


GradeOption = app_commands.Transform[Grade, GradeTransformer]
"""学年オプションの型。コマンドの引数の型注釈に使う"""
