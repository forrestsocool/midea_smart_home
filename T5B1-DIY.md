# T5B1 saved Meiju DIY programs

Version `26.9.4-b0-t5b1.3` builds on the BF mode-selection fix.

For model T5B1 / SN8 700XG241 with an existing Meiju account, the integration
imports the official app's saved DIY list at startup. It adds three entities:

- **DIY program**: select a saved program. Selection is local and does not start cooking.
- **Sync DIY programs**: refresh the list after editing a program in Meiju. It does not start cooking.
- **Start DIY program**: send all stages in one native LAN control command. Pressing this button starts the appliance.

The selected program's stages, support status, last synchronization time, and
device-reported current/total step are exposed as attributes of the selector.
Programs and selection are cached locally; cloud failures preserve the last
successful import. An empty successful response removes programs deleted in Meiju.

The cloud list is `/cloud-menu/midea/menu/dev/diymode/get/new`. It accepts success
code 200 (and 0) specifically for this request; existing cloud API behavior is
unchanged. Account credentials remain in the existing config entry and are not
included in the DIY cache.

This first version supports one to three stages using `pure_steam_1` and
`hot_wind_tube_fan_1`, scalar temperature settings, durations, automatic/manual
stage transitions, and the official `preheat` / `hotwind` options. Other modes
or extension fields remain visible with an unsupported reason and cannot start.
Their different parameter schemas must be adapted before enabling execution.

Starting requires an idle, connected appliance, a closed door, and a present
water tank with water. Before sending, the installed Lua codec must successfully
encode the command. The program uses the cloud's actual settings without any
invented temperature or duration. Multi-stage commands use `cookings`, `totalstep`,
`stepnum_start`, and `cloudmenuid`; transitions run on the appliance.

Standard HA actions can call the program from a script:

```yaml
sequence:
  - action: select.select_option
    target:
      entity_id: select.midea_DEVICE_ID_diy_program
    data:
      option: YOUR_SAVED_PROGRAM_NAME
  - action: button.press
    target:
      entity_id: button.midea_DEVICE_ID_diy_start
mode: single
```

Run tests in a Python environment with Home Assistant and the integration's
dependencies: `python -m unittest discover -s tests -v`. Tests mock all device
commands and cloud responses. The installed T5B1 Lua codec was also checked
offline: a two-stage command encoded the expected modes, temperatures, durations,
auto-next flag, menu ID, length, and checksum. No live cooking cycle was run.

Keep a backup of the installed integration. Restart Home Assistant after updating
Python files. An upstream HACS update may overwrite this custom build.

## Current temperature

The 700XG241 Lua codec reports `cur_temperature_above` and
`cur_temperature_underside`, but no separate `cur_temperature`. The T5B1-specific
mapping now reads the upper measured channel for the existing Current temperature
entity, matching the official plugin's cavity-temperature feedback source. Its
`source_attribute` identifies the source. The setpoint is never substituted and
readings above the setpoint are not clamped; missing readings remain unknown.
Other BF models retain their existing mapping and the entity ID is unchanged.
