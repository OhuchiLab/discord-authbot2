"""
database.DatabaseController の偽物

ファイルを使わず、学生情報をメモリ上だけに保持します。
"""

from several_types import StudentInfo


class InMemoryDatabase:
    """
    DatabaseController の偽物

    Attributes:
        save_count (int): save() が呼ばれた回数
    """

    def __init__(self, students: list[StudentInfo] | None = None):
        self._students: list[StudentInfo] = list(students or [])
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

    def update(self, student: StudentInfo) -> None:
        for index, current in enumerate(self._students):
            if current.uuid == student.uuid:
                self._students[index] = student
                self.save()
                return
        raise KeyError(f"uuid {student.uuid} は存在しません")

    def save(self) -> None:
        self.save_count += 1
