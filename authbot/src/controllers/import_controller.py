"""
CSV から学生情報を一括登録するコントローラー (/import_students で使う)

流れ:

    1. parse()   CSV を読み取り、登録する学生と、行ごとの問題を調べる (この時点では何も登録しない)
    2. commit()  問題が無ければ、全員をまとめて登録する (1 人でも問題があれば何も登録しない)

CSV の形式:

    - 1 行目は見出し。「氏名」「学籍番号」「学年」「メールアドレス」の列が必要 (順番は自由、ほかの列は無視する)
      → /export_students で書き出した CSV と同じ形でよい
    - 文字コードは UTF-8 (BOM の有無は問わない) か Shift_JIS (日本語版 Excel の「CSV」形式)
    - すべての欄が空の行は読み飛ばす
"""

import csv
import io
import logging

from several_types import Grade, ImportRow, NewStudent, StudentImportPlan, StudentInfo
from utils import normalize_email, normalize_input, normalize_student_number

from .student_controller import StudentController, StudentRegistrationError

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["氏名", "学籍番号", "学年", "メールアドレス"]
"""CSV に必要な列 (1 行目の見出し)"""

ENCODINGS = ["utf-8-sig", "cp932"]
"""試す文字コードの順番 (utf-8-sig は BOM の有無どちらも読める。cp932 は Windows の Shift_JIS)"""

MAX_ROWS = 500
"""1 回で登録できる学生の数"""


class StudentImportError(Exception):
    """
    一括登録ができないときに送出される例外

    メッセージはそのまま Discord 上で管理者に表示されます。
    """


class ImportController:
    """
    CSV を読み取り、学生情報をまとめて登録するクラス
    """

    def __init__(self, student_controller: StudentController):
        """
        コンストラクタ

        Args:
            student_controller (StudentController): 入力のチェックと登録に使う
        """
        self._students = student_controller

    def parse(self, data: bytes) -> StudentImportPlan:
        """
        CSV を読み取り、登録する学生と行ごとの問題を調べる。登録はしない

        Args:
            data (bytes): CSV ファイルの中身

        Returns:
            StudentImportPlan: 登録する学生 (rows) と、行ごとの問題 (errors)

        Raises:
            StudentImportError: ファイル全体の問題 (空・文字コード・列が足りない・学生がいない・多すぎる)
        """
        records = list(csv.reader(io.StringIO(self._decode(data))))
        if not records:
            raise StudentImportError("CSV が空です。")

        header = [normalize_input(cell) for cell in records[0]]
        missing = [column for column in REQUIRED_COLUMNS if column not in header]
        if missing:
            raise StudentImportError(f"CSV の 1 行目に、次の列がありません: {', '.join(missing)}")
        column_index = {column: header.index(column) for column in REQUIRED_COLUMNS}

        rows: list[ImportRow] = []
        errors: list[str] = []
        for line, record in enumerate(records[1:], start=2):
            if all(not cell.strip() for cell in record):
                continue  # 空の行
            values = {column: record[index] if index < len(record) else "" for column, index in column_index.items()}
            grade = Grade.parse(values["学年"])
            if grade is None:
                errors.append(
                    f"{line} 行目: 学年 「{normalize_input(values['学年'])}」 は使えません。"
                    f"{Grade.choices_text()} のいずれかにしてください。"
                )
                continue
            student = NewStudent(
                name=values["氏名"], student_number=values["学籍番号"], grade=grade, email=values["メールアドレス"]
            )
            rows.append(ImportRow(line=line, student=student))

        if not rows and not errors:
            raise StudentImportError("CSV に登録する学生がいません。")
        if len(rows) + len(errors) > MAX_ROWS:
            raise StudentImportError(f"1 回で登録できるのは {MAX_ROWS} 人までです。CSV を分けてください。")

        errors += self._find_row_problems(rows)
        errors.sort(key=lambda error: int(error.split(" ", 1)[0]))
        return StudentImportPlan(rows=rows, errors=errors)

    def commit(self, plan: StudentImportPlan) -> list[StudentInfo]:
        """
        計画の学生をまとめて登録する

        Args:
            plan (StudentImportPlan): `parse()` の結果

        Returns:
            list[StudentInfo]: 登録した学生情報

        Raises:
            StudentImportError: 計画に問題がある、または確認している間に重複が生じた場合 (何も登録しない)
        """
        if plan.errors:
            raise StudentImportError("CSV に問題があるため登録できません。")
        try:
            registered = self._students.register_students([row.student for row in plan.rows])
        except StudentRegistrationError as error:
            raise StudentImportError(
                f"確認している間に学生情報が変わったため、登録できませんでした ({error}) 。"
                "もう一度 /import_students からやり直してください。"
            ) from error
        logger.info("Imported %d students", len(registered))
        return registered

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    def _decode(self, data: bytes) -> str:
        """CSV のバイト列を文字列にする (UTF-8 → Shift_JIS の順に試す)"""
        for encoding in ENCODINGS:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise StudentImportError("CSV の文字コードを読み取れません。UTF-8 か Shift_JIS で保存してください。")

    def _find_row_problems(self, rows: list[ImportRow]) -> list[str]:
        """
        行ごとの問題を「N 行目: 〜」の形で返す

        CSV の中での重複はここで (CSV の行番号がわかる言い方で) 調べ、
        値の形式と登録済みの学生との重複は `StudentController.find_registration_problems()` で調べる
        """
        errors: list[str] = []
        first_line_of: dict[tuple[str, str], int] = {}
        unique_rows: list[ImportRow] = []
        for row in rows:
            keys = [
                ("学籍番号", normalize_student_number(row.student.student_number)),
                ("メールアドレス", normalize_email(row.student.email)),
            ]
            duplicate = next((key for key in keys if key in first_line_of), None)
            if duplicate is not None:
                label, value = duplicate
                errors.append(
                    f"{row.line} 行目: {label} {value} が CSV の中で重複しています ({first_line_of[duplicate]} 行目と同じ)。"
                )
                continue
            for key in keys:
                first_line_of[key] = row.line
            unique_rows.append(row)

        problems = self._students.find_registration_problems([row.student for row in unique_rows])
        errors += [f"{unique_rows[index].line} 行目: {problem}" for index, problem in problems.items()]
        return errors
