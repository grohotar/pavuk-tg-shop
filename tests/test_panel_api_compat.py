import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.services.panel_api_service import PanelApiService


class PanelApiCompatibilityTest(unittest.IsolatedAsyncioTestCase):
    def make_service(self):
        return PanelApiService(
            SimpleNamespace(PANEL_API_URL="https://panel.example/api", PANEL_API_KEY="test")
        )

    async def test_v2_uses_uuid_contract(self):
        service = self.make_service()
        service._request = AsyncMock(
            side_effect=[
                {"response": {"version": "2.7.4"}},
                {"response": [{"id": 7, "uuid": "old-uuid"}]},
                {"response": {"uuid": "old-uuid", "status": "ACTIVE"}},
                {"response": {"total": 0, "devices": []}},
            ]
        )

        users = await service.get_users_by_filter(telegram_id=123, log_response=False)
        await service.update_user_details_on_panel("old-uuid", {"status": "ACTIVE"})
        await service.disconnect_device("old-uuid", "device")

        self.assertEqual(users[0]["uuid"], "old-uuid")
        self.assertEqual(service._request.await_args_list[1].args[1], "/users/by-telegram-id/123")
        self.assertEqual(service._request.await_args_list[2].kwargs["json"]["uuid"], "old-uuid")
        self.assertEqual(
            service._request.await_args_list[3].kwargs["json"]["userUuid"], "old-uuid"
        )

    async def test_v3_uses_numeric_id_contract(self):
        service = self.make_service()
        service._request = AsyncMock(
            side_effect=[
                {"response": {"version": "3.3.2"}},
                {
                    "response": {
                        "users": [{"id": 42, "shortUuid": "short"}],
                        "nextCursor": None,
                        "hasMore": False,
                    }
                },
                {"response": {"id": 42, "status": "ACTIVE"}},
                {"response": {"total": 0, "devices": []}},
            ]
        )

        users = await service.get_users_by_filter(telegram_id=123, log_response=False)
        await service.update_user_details_on_panel(42, {"status": "ACTIVE"})
        await service.disconnect_device(42, "device")

        self.assertEqual(users[0]["id"], 42)
        self.assertEqual(service._request.await_args_list[1].args[1], "/users/stream")
        self.assertEqual(service._request.await_args_list[1].kwargs["params"]["telegramId"], "123")
        self.assertEqual(service._request.await_args_list[2].kwargs["json"]["id"], 42)
        self.assertEqual(service._request.await_args_list[3].kwargs["json"]["userId"], 42)

    async def test_running_bot_redetects_panel_upgrade(self):
        service = self.make_service()
        service._request = AsyncMock(
            side_effect=[
                {"response": {"version": "2.7.4"}},
                {"response": {"version": "3.3.2"}},
            ]
        )

        self.assertEqual(
            await service.resolve_user_ref(user_uuid="old-uuid", user_id=42),
            "old-uuid",
        )
        service._api_major_checked_at = -1000
        self.assertEqual(
            await service.resolve_user_ref(user_uuid="old-uuid", user_id=42),
            42,
        )


if __name__ == "__main__":
    unittest.main()
