"""
学生情報をファイルに書き出すコントローラー (/export_students で使う)

| 形式 | 用途 | 中身 |
| --- | --- | --- |
| CSV | Excel などで確認する | 見出し + 1 人 1 行 (学年順)。Excel で文字化けしないよう BOM 付きの UTF-8 |
| msgpack | バックアップ・復元 | 学生情報ファイルとまったく同じ内容 (そのまま学生情報ファイルとして使える) |
"""

import csv
import io
from collections.abc import Callable
from datetime import date

from database import DatabaseController
from several_types import ExportedFile

from .student_controller import sort_students

CSV_HEADER = ["氏名", "学籍番号", "学年", "メールアドレス", "Discord ID", "uuid"]
"""CSV の見出し"""


class ExportController:
    """
    学生情報を CSV / msgpack のファイルにするクラス
    """

    def __init__(self, database: DatabaseController, today: Callable[[], date] = date.today):
        """
        コンストラクタ

        Args:
            database (DatabaseController): 学生情報データベース
            today (Callable[[], date]): 今日の日付を返す関数 (ファイル名に使う。テストで差し替えるため)
        """
        self._database = database
        self._today = today

    def export_csv(self) -> ExportedFile:
        """
        学生情報を CSV にする

        Returns:
            ExportedFile: "students-YYYYMMDD.csv"
        """
        students = sort_students(self._database.get_all())
        text = io.StringIO()
        writer = csv.writer(text, lineterminator="\r\n")
        writer.writerow(CSV_HEADER)
        for student in students:
            writer.writerow(
                [
                    student.name,
                    student.student_number,
                    student.grade.value,
                    student.email,
                    student.discord_id or "",
                    student.uuid,
                ]
            )
        return ExportedFile(
            filename=f"students-{self._date_text()}.csv",
            data=text.getvalue().encode("utf-8-sig"),
            student_count=len(students),
        )

    def export_msgpack(self) -> ExportedFile:
        """
        学生情報ファイルと同じ内容の msgpack にする

        Returns:
            ExportedFile: "students-YYYYMMDD.msgpack"
        """
        return ExportedFile(
            filename=f"students-{self._date_text()}.msgpack",
            data=self._database.dump(),
            student_count=len(self._database.get_all()),
        )

    def _date_text(self) -> str:
        return self._today().strftime("%Y%m%d")
