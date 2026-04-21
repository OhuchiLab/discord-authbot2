"""
データベースの操作を行う I/F クラス定義
"""


class DatabaseController:
    """
    データベースの操作を行う I/F クラス
    """

    instance_ = None

    def __new__(cls, filepath):
        """
        コンストラクタ

        filepath (str): データベースの情報を保存するファイルの絶対パス
        """
        if cls.instance_ is None:
            cls.instance_ = super().__new__(cls)
            cls.instance_.filepath = filepath
        return cls.instance_

    def save(self):
        """
        データベースを保存する
        """
