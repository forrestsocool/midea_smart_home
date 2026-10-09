"""Meiju cloud schema and T5B1 multi-stage commands, without a live appliance."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("midea_diy", ROOT / "custom_components/midea_smart_home/midea_lib/diy.py")
DIY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIY)


def fixture():
    # Anonymized structure returned by the official T5B1 plugin's DIY API.
    return {"id": "program-1", "name": "Saved program", "modeCode": "9001", "userId": "private-user", "stages": [
        {"id": "stage-1", "stage": 1, "modeKey": "pure_steam_1", "setting": "100", "hour": 0, "minute": 1, "second": 0, "ext": "", "autoNextCook": 1},
        {"id": "stage-2", "stage": 2, "modeKey": "hot_wind_tube_fan_1", "setting": "80", "hour": 0, "minute": 20, "second": 0, "ext": "", "autoNextCook": 0},
    ]}


class DiyProgramTests(unittest.TestCase):
    def test_native_command_preserves_both_stages(self):
        control = DIY.build_diy_control(fixture())
        self.assertEqual(control["totalstep"], "2")
        self.assertEqual(control["stepnum_start"], "1")
        self.assertEqual(control["cloudmenuid"], "9001")
        stages = json.loads(control["cookings"])
        self.assertEqual([(s["work_mode"], s["temperature"], s["work_minute"]) for s in stages],
                         [("pure_steam_1", 100, 1), ("hot_wind_tube_fan_1", 80, 20)])
        self.assertEqual(stages[0]["workend"], "auto_next")
        self.assertEqual(stages[1]["workend"], "user_confirm_next")
        self.assertNotIn("work_mode", control)

    def test_normalization_removes_private_fields_and_is_repeatable(self):
        program = DIY.normalize_diy_programs({"hisRes": [fixture()]})[0]
        self.assertTrue(program["supported"])
        self.assertNotIn("userId", program)
        self.assertNotIn("id", program["stages"][0])
        self.assertEqual(DIY.normalize_diy_programs({"hisRes": [program]}), [program])

    def test_single_stage_uses_single_cooking_command(self):
        program = fixture()
        program["stages"] = program["stages"][:1]
        control = DIY.build_diy_control(program)
        self.assertNotIn("cookings", control)
        self.assertEqual(control["temperature"], 100)

    def test_manual_transition_is_preserved(self):
        program = fixture()
        program["stages"][0]["autoNextCook"] = 0
        self.assertEqual(json.loads(DIY.build_diy_control(program)["cookings"])[0]["workend"], "user_confirm_next")

    def test_extensions_are_preserved(self):
        program = fixture()
        program["stages"][0]["ext"] = "preheat,hotwind"
        step = json.loads(DIY.build_diy_control(program)["cookings"])[0]
        self.assertEqual(step["pre_heat"], "on")
        self.assertEqual(step["hot_wind"], "on")

    def test_bad_inputs_are_visible_but_cannot_run(self):
        for field, value in [("modeKey", "microwave_1"), ("setting", "100,80"), ("setting", 999),
                             ("minute", 60), ("hour", -1), ("second", True), ("autoNextCook", None),
                             ("ext", "steam3"), ("stage", 2)]:
            with self.subTest(field=field, value=value):
                program = fixture()
                program["stages"][0][field] = value
                with self.assertRaises(ValueError):
                    DIY.build_diy_control(program)
                parsed = DIY.normalize_diy_programs({"hisRes": [program]})[0]
                self.assertFalse(parsed["supported"])
                self.assertTrue(parsed["unsupported_reason"])

    def test_empty_zero_duration_missing_and_extra_stages_are_rejected(self):
        for stages in [[], None, [None], fixture()["stages"] * 2]:
            program = fixture()
            program["stages"] = stages
            with self.assertRaises(ValueError):
                DIY.build_diy_control(program)
        program = fixture()
        program["stages"][0]["minute"] = 0
        with self.assertRaises(ValueError):
            DIY.build_diy_control(program)

    def test_malformed_cloud_response_does_not_replace_valid_cache(self):
        for response in [{}, {"hisRes": None}, {"hisRes": [None]}, {"hisRes": [fixture(), deepcopy(fixture())]}]:
            with self.assertRaises(ValueError):
                DIY.normalize_diy_programs(response)


if __name__ == "__main__":
    unittest.main()
