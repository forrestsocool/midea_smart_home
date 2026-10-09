"""Replay BF temperature status through real mapping and sensor setup."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from homeassistant.const import Platform

ROOT = Path(__file__).resolve().parents[1]
for name, directory in [
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.midea_smart_home", ROOT / "custom_components/midea_smart_home"),
]:
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(directory)]
        sys.modules[name] = package
SENSOR = importlib.import_module("custom_components.midea_smart_home.sensor")
MAPPING = importlib.import_module("custom_components.midea_smart_home.device_mapping")


class BfTemperatureTests(unittest.IsolatedAsyncioTestCase):
    async def make_entities(self, data, model="T5B1", sn8="700XG241"):
        coordinator = Mock()
        coordinator.data = data
        coordinator.device.available = True
        coordinator.last_update_success = True
        coordinator.diy_programs = None
        mapping = MAPPING.get_device_mapping(0xBF, model, sn8, "microwave_steam_oven")
        entities = []
        with patch.object(SENSOR, "iter_midea_device_configs", return_value=[
            (coordinator, 123, "0xBF", "fixture-sn", sn8, "Fixture oven", model, mapping)
        ]):
            await SENSOR.async_setup_entry(Mock(), Mock(), entities.extend)
        return coordinator, {e._entity_key: e for e in entities}

    async def test_current_temperature_uses_reported_upper_channel(self):
        # These are the two physical fields emitted by T0xBF_700XG241.lua.
        coordinator, entities = await self.make_entities({
            "cur_temperature_above": 95, "cur_temperature_underside": 0, "temperature": 80,
        })
        self.assertEqual(entities["cur_temperature"].native_value, 95)
        coordinator.data["cur_temperature_above"] = 87
        self.assertEqual(entities["cur_temperature"].native_value, 87)
        self.assertEqual(entities["cur_temperature_above"].native_value, 87)

    async def test_setpoint_is_never_substituted_for_actual_temperature(self):
        _, entities = await self.make_entities({"temperature": 80, "cur_temperature_underside": 0})
        self.assertIsNone(entities["cur_temperature"].native_value)

    async def test_zero_and_missing_temperature_remain_distinct(self):
        coordinator, entities = await self.make_entities({"cur_temperature_above": 0})
        self.assertEqual(entities["cur_temperature"].native_value, 0)
        coordinator.data["cur_temperature_above"] = None
        self.assertIsNone(entities["cur_temperature"].native_value)

    async def test_offline_sensor_is_unavailable(self):
        coordinator, entities = await self.make_entities({"cur_temperature_above": 95})
        coordinator.device.available = False
        self.assertIsNone(entities["cur_temperature"].native_value)

    async def test_other_bf_models_keep_their_own_current_temperature(self):
        _, entities = await self.make_entities({"cur_temperature": 42, "cur_temperature_above": 95}, "Other model", "OTHER123")
        self.assertEqual(entities["cur_temperature"].native_value, 42)
        generic = MAPPING.get_device_mapping(0xBF, "Other model", "OTHER123", "microwave_steam_oven")
        self.assertNotIn("status_key", generic["entities"][Platform.SENSOR]["cur_temperature"])


if __name__ == "__main__":
    unittest.main()
