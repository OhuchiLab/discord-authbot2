"""
テストから時刻を進められる時計
"""

from datetime import datetime, timedelta


class FakeClock:
    """
    `now()` が返す時刻を、テストから `advance()` で進められる時計
    """

    def __init__(self, start: datetime = datetime(2026, 4, 1, 9, 0)):
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> None:
        """
        時刻を進める (引数は timedelta と同じ。例: advance(minutes=10))
        """
        self.current += timedelta(**kwargs)
