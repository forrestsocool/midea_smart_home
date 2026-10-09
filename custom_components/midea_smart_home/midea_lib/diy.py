"""Convert Meiju DIY programs to the verified T5B1 multi-stage protocol."""

import json
from copy import deepcopy

# Verified against the official 700XG241 plugin and the installed BF Lua codec.
# Other mode schemas must be adapted before they can be executed.
SUPPORTED_MODES = {"pure_steam_1", "hot_wind_tube_fan_1"}
MAX_STAGES = 3


def _integer(value, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"Invalid {name}")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {name}") from None
    if not minimum <= result <= maximum:
        raise ValueError(f"Invalid {name}")
    return result


def build_diy_control(program: dict) -> dict:
    """Build one native command. Reject unsupported fields rather than omit them."""
    stages = program.get("stages")
    if not isinstance(stages, list) or not 1 <= len(stages) <= MAX_STAGES:
        raise ValueError("Expected one to three DIY stages")
    steps = []
    for index, stage in enumerate(stages, 1):
        if not isinstance(stage, dict):
            raise ValueError("Invalid DIY stage")
        if _integer(stage.get("stage"), "stage", 1, MAX_STAGES) != index:
            raise ValueError("DIY stages must be in consecutive order")
        mode = stage.get("modeKey")
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported DIY mode: {mode}")
        hour = _integer(stage.get("hour"), "hour", 0, 23)
        minute = _integer(stage.get("minute"), "minute", 0, 59)
        second = _integer(stage.get("second"), "second", 0, 59)
        if hour * 3600 + minute * 60 + second == 0:
            raise ValueError("DIY duration must be greater than zero")
        # For these two modes the official plugin interprets setting as Celsius.
        temperature = _integer(stage.get("setting"), "temperature", 30, 250)
        auto_next = _integer(stage.get("autoNextCook"), "autoNextCook", 0, 1)
        step = {
            "stepnum": index, "work_mode": mode, "temperature": temperature,
            "work_hour": hour, "work_minute": minute, "work_second": second,
            "workend": "auto_next" if auto_next else "user_confirm_next",
        }
        ext = stage.get("ext") or ""
        if not isinstance(ext, str):
            raise ValueError("Invalid DIY extension")
        for option in filter(None, ext.split(",")):
            if option == "preheat":
                step["pre_heat"] = "on"
            elif option == "hotwind":
                step["hot_wind"] = "on"
            else:
                raise ValueError(f"Unsupported DIY option: {option}")
        steps.append(step)
    menu_id = _integer(program.get("modeCode") or "9999", "modeCode", 1, 0xFFFFFF)
    if len(steps) == 1:
        return {**steps[0], "cloudmenuid": str(menu_id)}
    return {
        "totalstep": str(len(steps)), "stepnum_start": "1",
        "cloudmenuid": str(menu_id),
        "cookings": json.dumps(steps, ensure_ascii=False, separators=(",", ":")),
    }


def normalize_diy_programs(response: dict) -> list[dict]:
    """Keep only program metadata, never account identifiers or credentials."""
    if not isinstance(response, dict) or not isinstance(response.get("hisRes"), list):
        raise ValueError("Unexpected Meiju DIY response")
    programs = []
    identifiers = set()
    for item in response["hisRes"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid Meiju DIY program")
        identifier = item.get("modeId") or item.get("id")
        name = item.get("name")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("Invalid or duplicate DIY program ID")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Invalid DIY program name")
        identifiers.add(identifier)
        stages = item.get("stages")
        if isinstance(stages, list):
            stages = [
                {key: deepcopy(stage[key]) for key in (
                    "name", "modeKey", "stage", "setting", "hour", "minute", "second", "ext", "autoNextCook"
                ) if key in stage} if isinstance(stage, dict) else None
                for stage in stages
            ]
        program = {"id": identifier, "name": name.strip(), "modeCode": item.get("modeCode"), "stages": stages}
        try:
            build_diy_control(program)
            program["supported"] = True
            program["unsupported_reason"] = None
        except ValueError as error:
            program["supported"] = False
            program["unsupported_reason"] = str(error)
        programs.append(program)
    return programs
