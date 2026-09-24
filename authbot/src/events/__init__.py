"""
Discord から届くイベントを処理するパッケージ。

`bot.AuthBot` の `on_xxx` メソッドから呼ばれます。1 イベントにつき 1 モジュールです。
各処理は Discord の情報 (ユーザー ID やメッセージ本文) を取り出して `controllers` に渡すだけです。

| モジュール | イベント | 渡す先 |
| --- | --- | --- |
| `on_ready` | Bot の準備完了 | `RoleController.setup_roles()` |
| `on_member_join` | メンバーの参加 | `OnboardingController.welcome_new_member()` |
| `on_message` | DM の受信 | `OnboardingController.receive_direct_message()` |
"""

from .on_member_join import handle_member_join
from .on_message import handle_message
from .on_ready import handle_ready
