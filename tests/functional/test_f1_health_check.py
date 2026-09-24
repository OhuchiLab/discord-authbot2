"""
[機能] F1 死活確認 (/health_check)
"""


async def test_誰が実行しても_Botが動いていることを返す(driver):
    driver.discord.add_member("111")
    assert await driver.run_command("111", "health_check") == "I'm alive!"
