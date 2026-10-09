"""Offline regression checks; no Home Assistant or device connection needed."""

import importlib.util
from pathlib import Path
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "midea_extras", ROOT / "custom_components/midea_smart_home/midea_lib/extras.py"
)
EXTRAS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRAS)


class BfControlTests(unittest.TestCase):
    def setUp(self):
        self.handler = EXTRAS.DeviceLogicHandler(0xBF, "T5B1")
        self.fields = ["work_mode", "temperature", "work_hour", "work_minute", "work_second"]
        self.status = {"work_mode": "microwave_1", "temperature": 180,
                       "work_hour": 0, "work_minute": 10, "work_second": 0}

    def prepare(self, control, recent=None):
        return self.handler.prepare_control_data(
            control.copy(), self.status, recent_controls=recent,
            control_timeout=5, centralized=self.fields
        )

    def test_mode_includes_temperature_and_time(self):
        result = self.prepare({"work_mode": "hot_wind_tube_fan_1"})
        self.assertEqual(result, {**self.status, "work_mode": "hot_wind_tube_fan_1"})

    def test_recent_temperature_wins_over_delayed_status(self):
        result = self.prepare({"work_mode": "hot_wind_tube_fan_1"},
                              {"temperature": (200, time.time())})
        self.assertEqual(result["temperature"], 200)

    def test_expired_temperature_uses_device_status(self):
        result = self.prepare({"work_mode": "hot_wind_tube_fan_1"},
                              {"temperature": (200, time.time() - 60)})
        self.assertEqual(result["temperature"], 180)

    def test_explicit_parameters_win(self):
        result = self.prepare({"work_mode": "hot_wind_tube_fan_1", "temperature": 160},
                              {"temperature": (200, time.time())})
        self.assertEqual(result["temperature"], 160)

    def test_stop_pause_resume_and_lock_stay_single_purpose(self):
        for control in [{"work_status": "standby"}, {"work_status": "pause"},
                        {"work_status": "work"}, {"lock": "on"}]:
            with self.subTest(control=control):
                self.assertEqual(self.prepare(control), control)

    def test_missing_parameters_are_not_invented(self):
        self.status = {}
        self.assertEqual(self.prepare({"work_mode": "hot_wind_tube_fan_1"}),
                         {"work_mode": "hot_wind_tube_fan_1"})

    def test_other_device_types_unchanged(self):
        self.handler = EXTRAS.DeviceLogicHandler(0xAC, "AC")
        self.assertEqual(self.prepare({"work_mode": "hot_wind_tube_fan_1"}),
                         {"work_mode": "hot_wind_tube_fan_1"})


if __name__ == "__main__":
    unittest.main()
