"""Saved Meiju DIY programs: cloud refresh, local selection, native execution."""

import asyncio
import logging
from datetime import datetime, UTC

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .midea_lib.cloud import get_midea_cloud
from .midea_lib.diy import build_diy_control, normalize_diy_programs

_LOGGER = logging.getLogger(__name__)


class MideaDiyPrograms:
    """Store imported programs and send all stages in a single device command."""

    def __init__(self, hass, entry, coordinator, device_id: int, sn8: str):
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.device_id = device_id
        self.sn8 = sn8
        self.programs = []
        self.selected_id = None
        self.last_sync = None
        self.last_error = None
        self._lock = asyncio.Lock()
        self._store = Store(hass, 1, f"midea_smart_home.diy_{device_id}")

    @property
    def options(self):
        names = [p["name"] for p in self.programs]
        return [p["name"] if names.count(p["name"]) == 1 else f'{p["name"]} ({p["id"]})' for p in self.programs]

    @property
    def selected(self):
        return next((p for p in self.programs if p["id"] == self.selected_id), None)

    @property
    def current_option(self):
        return next((name for name, p in zip(self.options, self.programs) if p["id"] == self.selected_id), None)

    async def async_initialize(self):
        saved = await self._store.async_load() or {}
        # Revalidate cached records with the current parser on every load.
        try:
            self.programs = normalize_diy_programs({"hisRes": saved.get("programs", [])})
            self.selected_id = saved.get("selected_id")
            self.last_sync = saved.get("last_sync")
        except ValueError:
            self.programs = []
        try:
            await self.async_refresh()
        except HomeAssistantError:
            _LOGGER.warning("Could not refresh DIY programs for device %s; keeping cached programs", self.device_id)

    async def _save(self):
        await self._store.async_save({"programs": self.programs, "selected_id": self.selected_id, "last_sync": self.last_sync})

    def _notify(self):
        self.coordinator.async_update_listeners()

    async def async_select(self, option):
        if option not in self.options:
            raise HomeAssistantError("Unknown DIY program")
        self.selected_id = self.programs[self.options.index(option)]["id"]
        await self._save()
        self._notify()

    async def async_refresh(self):
        async with self._lock:
            try:
                cloud = get_midea_cloud(
                    "Meiju Cloud", async_get_clientsession(self.hass),
                    self.entry.data["account"], self.entry.data["password"],
                )
                if not await cloud.login():
                    raise HomeAssistantError("Meiju login failed")
                response = await cloud.list_diy_programs(
                    self.device_id, self.sn8, (self.coordinator.data or {}).get("cbs_version", ""),
                )
                if response is None:
                    raise HomeAssistantError("Meiju DIY query failed")
                programs = normalize_diy_programs(response)
                self.programs = programs
                if not self.selected:
                    self.selected_id = programs[0]["id"] if len(programs) == 1 else None
                self.last_sync = datetime.now(UTC).isoformat()
                self.last_error = None
                await self._save()
            except (ValueError, KeyError, HomeAssistantError) as error:
                self.last_error = "Unable to refresh Meiju DIY programs"
                raise HomeAssistantError(self.last_error) from error
            finally:
                self._notify()

    async def async_run(self):
        async with self._lock:
            program = self.selected
            if not program:
                raise HomeAssistantError("Select a DIY program first")
            try:
                control = build_diy_control(program)
            except ValueError as error:
                raise HomeAssistantError(str(error)) from error
            status = self.coordinator.data or {}
            if not self.coordinator.device.available:
                raise HomeAssistantError("Appliance is offline")
            if status.get("work_status") not in {"standby", "save_power"}:
                raise HomeAssistantError("Appliance must be idle before starting a DIY program")
            if status.get("door_open") != "off":
                raise HomeAssistantError("Appliance door must be closed")
            if status.get("lack_water") != 0 or status.get("lack_box") != 0:
                raise HomeAssistantError("Check the appliance water tank before starting")
            # Preflight the installed codec offline; selection and sync never send commands.
            await self.hass.async_add_executor_job(self._validate_codec, control)
            await self.coordinator.async_set_controls(control)

    def _validate_codec(self, control):
        device = self.coordinator.device
        payload = device._codec.build_control(control, current_status=device.data)
        if not payload:
            raise HomeAssistantError("Appliance codec could not encode this DIY program")
