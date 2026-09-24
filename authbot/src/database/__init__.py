"""
学生情報を管理するパッケージ。

このパッケージは、学生情報データベースに関する以下の操作を行います。

- ファイルからの読み込み (起動時)
- 学生情報の検索 (uuid / Discord ID)
- 学生情報の追加・更新と、ファイルへの保存
"""

from .database_controller import DatabaseController
