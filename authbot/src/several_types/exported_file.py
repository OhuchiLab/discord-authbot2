"""
書き出したファイル (/export_students で管理者に渡すもの) のデータクラス定義
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportedFile:
    """
    書き出したファイル

    Attributes:
        filename (str): ファイル名 (例: "students-20270301.csv")
        data (bytes): ファイルの中身
        student_count (int): 含まれる学生の人数
    """

    filename: str
    data: bytes
    student_count: int
