"""
学生情報を管理するパッケージ。

このパッケージは、学生情報データベースに関する以下の操作を行います。

- ファイルからの読み込み (起動時)
- 学生情報の検索 (uuid / Discord ID)
- 学生情報の追加・更新・削除と、ファイルへの保存
- 学生情報ファイルの自動バックアップ (`DatabaseBackup`)
"""

from .database_backup import DatabaseBackup
from .database_controller import DatabaseController, open_database
