"""
データベースの操作を行う I/F クラス定義

学生情報は msgpack 形式で 1 つのファイルに保存します。
起動時にファイル全体をメモリへ読み込み、変更があるたびにファイル全体を書き直します。
(研究室のメンバー数程度であれば、この方式で十分高速です)
"""

import os
import tempfile
from pathlib import Path

import msgpack

from several_types import StudentInfo


class DatabaseController:
    """
    データベースの操作を行う I/F クラス

    このクラスは「保存・読み込み・検索」だけを担当し、
    入力値のチェックや重複の判定は `controllers.StudentController` が行います。
    """

    def __init__(self, filepath: Path):
        """
        コンストラクタ。ファイルが存在すれば、その内容を読み込む

        Args:
            filepath (Path): データベースの情報を保存するファイルのパス
        """
        self._filepath = Path(filepath)
        self._students: list[StudentInfo] = self._load()

    def get_all(self) -> list[StudentInfo]:
        """
        登録されているすべての学生情報を返す

        Returns:
            list[StudentInfo]: 学生情報の一覧 (コピー)
        """
        return list(self._students)

    def find_by_uuid(self, uuid: str) -> StudentInfo | None:
        """
        uuid が一致する学生情報を返す。見つからなければ None
        """
        return next((s for s in self._students if s.uuid == uuid), None)

    def find_by_discord_id(self, discord_id: str) -> StudentInfo | None:
        """
        Discord ID が一致する学生情報を返す。見つからなければ None
        """
        return next((s for s in self._students if s.discord_id == discord_id), None)

    def add(self, student: StudentInfo) -> None:
        """
        学生情報を追加してファイルに保存する

        Args:
            student (StudentInfo): 追加する学生情報

        Raises:
            ValueError: 同じ uuid の学生情報がすでに存在する場合
        """
        if self.find_by_uuid(student.uuid) is not None:
            raise ValueError(f"uuid {student.uuid} はすでに存在します")
        self._students.append(student)
        self.save()

    def update(self, student: StudentInfo) -> None:
        """
        uuid が一致する学生情報を置き換えてファイルに保存する

        Args:
            student (StudentInfo): 更新後の学生情報

        Raises:
            KeyError: 同じ uuid の学生情報が存在しない場合
        """
        for index, current in enumerate(self._students):
            if current.uuid == student.uuid:
                self._students[index] = student
                self.save()
                return
        raise KeyError(f"uuid {student.uuid} は存在しません")

    def save(self) -> None:
        """
        メモリ上の学生情報をファイルに保存する

        書き込み途中で Bot が停止してもファイルが壊れないよう、
        一時ファイルに書き込んでから本来のファイル名に置き換えます。
        """
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        pack_data = [student.to_dict() for student in self._students]

        fd, temp_path = tempfile.mkstemp(dir=self._filepath.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                msgpack.pack(pack_data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self._filepath)
        except BaseException:
            os.remove(temp_path)
            raise

    def _load(self) -> list[StudentInfo]:
        """
        ファイルから学生情報を読み込む。ファイルが無ければ空のリストを返す
        """
        if not self._filepath.exists():
            return []
        with open(self._filepath, "rb") as f:
            pack_data = msgpack.unpack(f)
        return [StudentInfo.from_dict(data) for data in pack_data]
