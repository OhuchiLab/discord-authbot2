"""
database.DatabaseController の偽物

ファイルを使わず、学生情報をメモリ上だけに保持します。
"""

import msgpack

from several_types import StudentInfo


class InMemoryDatabase:
    """
    DatabaseController の偽物

    Attributes:
        save_count (int): save() が呼ばれた回数
    """

    def __init__(self, students: list[StudentInfo] | None = None):
        self._students: list[StudentInfo] = list(students or [])
        self._completed_fiscal_years: set[int] = set()
        self.save_count = 0

    def get_all(self) -> list[StudentInfo]:
        return list(self._students)

    def find_by_uuid(self, uuid: str) -> StudentInfo | None:
        return next((s for s in self._students if s.uuid == uuid), None)

    def find_by_discord_id(self, discord_id: str) -> StudentInfo | None:
        return next((s for s in self._students if s.discord_id == discord_id), None)

    def add(self, student: StudentInfo) -> None:
        if self.find_by_uuid(student.uuid) is not None:
            raise ValueError(f"uuid {student.uuid} はすでに存在します")
        self._students.append(student)
        self.save()

    def add_many(self, students: list[StudentInfo]) -> None:
        uuids = [student.uuid for student in students]
        if len(set(uuids)) != len(uuids) or any(self.find_by_uuid(uuid) is not None for uuid in uuids):
            raise ValueError("uuid が重複しています")
        self._students.extend(students)
        self.save()

    def update(self, student: StudentInfo) -> None:
        for index, current in enumerate(self._students):
            if current.uuid == student.uuid:
                self._students[index] = student
                self.save()
                return
        raise KeyError(f"uuid {student.uuid} は存在しません")

    def delete(self, uuid: str) -> None:
        for index, current in enumerate(self._students):
            if current.uuid == uuid:
                del self._students[index]
                self.save()
                return
        raise KeyError(f"uuid {uuid} は存在しません")

    def completed_fiscal_years(self) -> set[int]:
        return set(self._completed_fiscal_years)

    def commit_year_update(self, students: list[StudentInfo], fiscal_year: int) -> None:
        if fiscal_year in self._completed_fiscal_years:
            raise ValueError(f"{fiscal_year}年度はすでに実行済みです")
        indexes = {current.uuid: index for index, current in enumerate(self._students)}
        missing = [student.uuid for student in students if student.uuid not in indexes]
        if missing:
            raise KeyError(f"uuid {', '.join(missing)} は存在しません")
        for student in students:
            self._students[indexes[student.uuid]] = student
        self._completed_fiscal_years.add(fiscal_year)
        self.save()

    def dump(self) -> bytes:
        return msgpack.packb(
            {
                "format_version": 2,
                "students": [student.to_dict() for student in self._students],
                "completed_fiscal_years": sorted(self._completed_fiscal_years),
            }
        )

    def save(self) -> None:
        self.save_count += 1
