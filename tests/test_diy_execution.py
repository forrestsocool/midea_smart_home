"""HA integration boundary: refresh/select are read-only; start sends one command."""
import asyncio
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.exceptions import HomeAssistantError
from test_diy_programs import fixture

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("diy_test_integration")
package.__path__ = [str(ROOT / "custom_components/midea_smart_home")]
sys.modules[package.__name__] = package
MODULE = importlib.import_module("diy_test_integration.diy")


class DiyExecutionTests(unittest.IsolatedAsyncioTestCase):
    def manager(self):
        manager = object.__new__(MODULE.MideaDiyPrograms)
        manager.programs = MODULE.normalize_diy_programs({"hisRes": [fixture()]})
        manager.selected_id = "program-1"
        manager.last_sync = "previous"
        manager.last_error = None
        manager._lock = asyncio.Lock()
        manager._store = Mock(async_save=AsyncMock())
        manager.device_id = 123
        manager.sn8 = "700XG241"
        manager.hass = Mock()
        async def execute(function, *args):
            return function(*args)
        manager.hass.async_add_executor_job = execute
        manager.entry = Mock(data={"account": "fixture-account", "password": "fixture-password"})
        manager.coordinator = Mock()
        manager.coordinator.data = {"work_status": "standby", "door_open": "off", "lack_water": 0, "lack_box": 0}
        manager.coordinator.device.data = manager.coordinator.data
        manager.coordinator.device.available = True
        manager.coordinator.device._codec.build_control.return_value = "aa"
        manager.coordinator.async_set_controls = AsyncMock()
        return manager

    async def test_select_does_not_send_a_device_command(self):
        manager = self.manager()
        await manager.async_select("Saved program")
        manager.coordinator.async_set_controls.assert_not_awaited()

    async def test_start_sends_all_stages_once(self):
        manager = self.manager()
        await manager.async_run()
        manager.coordinator.async_set_controls.assert_awaited_once_with(MODULE.build_diy_control(manager.selected))

    async def test_busy_offline_open_door_unknown_and_lacking_water_are_blocked(self):
        for change in [{"work_status": "work"}, {"work_status": "pause"}, {"work_status": None},
                       {"door_open": "on"}, {"door_open": None}, {"lack_water": 1}, {"lack_box": 1}]:
            with self.subTest(change=change):
                manager = self.manager()
                manager.coordinator.data.update(change)
                with self.assertRaises(HomeAssistantError):
                    await manager.async_run()
                manager.coordinator.async_set_controls.assert_not_awaited()
        manager = self.manager()
        manager.coordinator.device.available = False
        with self.assertRaises(HomeAssistantError):
            await manager.async_run()
        manager.coordinator.async_set_controls.assert_not_awaited()

    async def test_codec_failure_cannot_send(self):
        manager = self.manager()
        manager.coordinator.device._codec.build_control.return_value = ""
        with self.assertRaises(HomeAssistantError):
            await manager.async_run()
        manager.coordinator.async_set_controls.assert_not_awaited()

    async def test_refresh_and_failure_preserve_selection_without_starting(self):
        manager = self.manager()
        cloud = Mock(login=AsyncMock(return_value=True), list_diy_programs=AsyncMock(return_value={"hisRes": [fixture()]}))
        with patch.object(MODULE, "async_get_clientsession"), patch.object(MODULE, "get_midea_cloud", return_value=cloud):
            await manager.async_refresh()
            self.assertEqual(manager.selected_id, "program-1")
            self.assertIsNone(manager.last_error)
            manager.coordinator.async_set_controls.assert_not_awaited()
            cloud.list_diy_programs.return_value = None
            with self.assertRaises(HomeAssistantError):
                await manager.async_refresh()
            self.assertEqual(manager.current_option, "Saved program")
            self.assertTrue(manager.last_error)
            manager.coordinator.async_set_controls.assert_not_awaited()

    async def test_empty_cloud_list_removes_deleted_program(self):
        manager = self.manager()
        cloud = Mock(login=AsyncMock(return_value=True), list_diy_programs=AsyncMock(return_value={"hisRes": []}))
        with patch.object(MODULE, "async_get_clientsession"), patch.object(MODULE, "get_midea_cloud", return_value=cloud):
            await manager.async_refresh()
        self.assertIsNone(manager.selected_id)
        self.assertEqual(manager.options, [])


if __name__ == "__main__":
    unittest.main()
