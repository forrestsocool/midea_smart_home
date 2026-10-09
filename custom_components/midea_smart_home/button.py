import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MideaCoordinator
from .entity import MideaBaseEntity, iter_midea_device_configs

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities = []

    for coordinator, device_id, device_type, sn, sn8, device_name, model, device_mapping in iter_midea_device_configs(
        hass, entry
    ):
        entities_config = device_mapping.get("entities", {})
        button_config = entities_config.get(Platform.BUTTON, {})

        if coordinator.diy_programs is not None:
            for action in ("diy_refresh", "diy_start"):
                entities.append(MideaDiyButton(
                    coordinator, device_id, device_type, sn, sn8, device_name, action, model,
                ))

        if button_config:
            for button_id, config in button_config.items():
                entities.append(
                    MideaButtonEntity(
                        coordinator, device_id, device_type, sn, sn8, device_name,
                        button_id, config, model
                    )
                )

    async_add_entities(entities)


class MideaDiyButton(MideaBaseEntity, ButtonEntity):
    def __init__(self, coordinator, device_id, device_type, sn, sn8, device_name, action, model):
        super().__init__(coordinator, device_id, device_type, sn, sn8, device_name,
                         action, model, platform_name="button")
        self.programs = coordinator.diy_programs
        self.action = action
        self._attr_icon = "mdi:cloud-sync" if action == "diy_refresh" else "mdi:play"

    @property
    def available(self):
        if self.action == "diy_refresh":
            return True
        return super().available and bool(self.programs.selected and self.programs.selected["supported"])

    async def async_press(self):
        if self.action == "diy_refresh":
            await self.programs.async_refresh()
        else:
            await self.programs.async_run()


class MideaButtonEntity(MideaBaseEntity, ButtonEntity):
    def __init__(
        self,
        coordinator: MideaCoordinator,
        device_id: int,
        device_type: str,
        sn: str,
        sn8: str,
        device_name: str,
        entity_key: str,
        config: dict,
        model: str = None,
    ):
        super().__init__(
            coordinator, device_id, device_type, sn, sn8, device_name, entity_key, model,
            platform_name="button", config=config
        )

    async def async_press(self) -> None:
        command = self._config.get("command")

        if command and isinstance(command, dict):
            await self.coordinator.async_set_control(command)
        else:
            _LOGGER.warning("Button %s has no command configured", self._entity_key)
