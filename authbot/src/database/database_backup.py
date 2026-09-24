"""
学生情報ファイルのバックアップ (日時付きのコピー) を作る

学生情報はローカルの 1 ファイルだけに保存しているため、誤操作やファイルの破損に備えて、
変更のたびに日時付きのコピーを残し、古いものから決められた数だけ残して消します。

    data/backups/students-20270301-093015-123456.msgpack
                 ~~~~~~~~ ~~~~~~~~~~~~~~~~~~~~~~ ~~~~~~~~
                 元の名前  コピーした日時           元の拡張子

復元するときは、Bot を止めてから、戻したいコピーを学生情報ファイルに上書きして起動します。
"""

import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S-%f"
"""コピーのファイル名に付ける日時の形式 (名前順に並べると古い順になる)"""


class DatabaseBackup:
    """
    学生情報ファイルのバックアップを作り、古いものを消すクラス
    """

    def __init__(self, backup_dir: Path, keep: int, now: Callable[[], datetime] = datetime.now):
        """
        コンストラクタ

        Args:
            backup_dir (Path): コピーの保存先のフォルダ (無ければ作る)
            keep (int): 残すコピーの数 (1 以上)
            now (Callable[[], datetime]): 現在時刻を返す関数 (テストで差し替えるため)

        Raises:
            ValueError: keep が 1 未満の場合
        """
        if keep < 1:
            raise ValueError("残すバックアップの数は 1 以上にしてください")
        self._backup_dir = Path(backup_dir)
        self._keep = keep
        self._now = now

    def create(self, source: Path) -> Path:
        """
        ファイルの日時付きのコピーを作り、古いコピーを消す

        書き込み途中で停止しても壊れたコピーが残らないよう、一時ファイルに書いてから名前を付けます。

        Args:
            source (Path): コピーする学生情報ファイル

        Returns:
            Path: 作ったコピー
        """
        source = Path(source)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        destination = self._backup_dir / f"{source.stem}-{self._now().strftime(TIMESTAMP_FORMAT)}{source.suffix}"

        fd, temp_path = tempfile.mkstemp(dir=self._backup_dir, prefix=".tmp-")
        os.close(fd)
        try:
            shutil.copyfile(source, temp_path)
            os.replace(temp_path, destination)
        except BaseException:
            os.remove(temp_path)
            raise

        self._remove_old_backups(source)
        logger.info("Created backup %s", destination)
        return destination

    def _remove_old_backups(self, source: Path) -> None:
        """同じ元ファイルのコピーのうち、新しい keep 個を残して消す"""
        backups = sorted(self._backup_dir.glob(f"{source.stem}-*{source.suffix}"))
        for old in backups[: -self._keep]:
            old.unlink()
