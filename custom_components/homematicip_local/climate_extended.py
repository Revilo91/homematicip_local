"""Extended climate platform for Homematic(IP) Local with linked switch support."""

from __future__ import annotations

import logging
from typing import Any

from aiohomematic.const import CALLBACK_TYPE
from aiohomematic.model.custom import BaseCustomDpClimate, ClimateActivity, ClimateMode
from homeassistant.components.climate import HVACAction
from homeassistant.core import callback

from .climate import AioHomematicClimate, HM_TO_HA_ACTION
from .control_unit import ControlUnit

_LOGGER = logging.getLogger(__name__)


class AioHomematicClimateWithLinkedSwitches(AioHomematicClimate):
    """Climate entity with linked switch awareness for HVAC action determination."""

    def __init__(
        self,
        control_unit: ControlUnit,
        data_point: BaseCustomDpClimate,
    ) -> None:
        """Initialize the extended climate entity."""
        super().__init__(control_unit=control_unit, data_point=data_point)
        self._linked_switches: dict[str, Any] = {}
        self._linked_switch_callbacks: dict[str, CALLBACK_TYPE] = {}

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        await self.async_reload_linked_switches()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self._unregister_linked_switch_callbacks()

    async def async_reload_linked_switches(self) -> None:
        """Reload linked switches discovery."""
        self._unregister_linked_switch_callbacks()
        self._linked_switches = {}

        try:
            # Get channel address for this climate entity
            channel_address = self._data_point.channel.address

            # Query parameter links via device client
            link_peers = await self._data_point.device.client.get_link_peers(address=channel_address)

            if not link_peers:
                _LOGGER.debug(
                    "No link peers found for %s (%s)",
                    self.entity_id,
                    channel_address,
                )
                return

            # Discover linked channels and find DpSwitch data points
            for peer_address in link_peers:
                try:
                    # Get the device for this peer address
                    peer_device = self._data_point.device.central.get_device(address=peer_address.split(":")[0])
                    if not peer_device:
                        _LOGGER.debug("Could not find device for peer %s", peer_address)
                        continue

                    # Get the channel
                    channel_no = int(peer_address.split(":")[1])
                    peer_channel = peer_device.get_channel(channel_no)
                    if not peer_channel:
                        _LOGGER.debug("Could not find channel for peer %s", peer_address)
                        continue

                    # Look for STATE parameter (DpSwitch)
                    for data_point in peer_channel.data_points.values():
                        if hasattr(data_point, "parameter") and data_point.parameter == "STATE":
                            # Register this as a linked switch
                            self._linked_switches[peer_address] = data_point

                            # Register callback for state changes
                            def make_callback(dp_address: str) -> CALLBACK_TYPE:
                                @callback
                                def _callback(*args: Any, **kwargs: Any) -> None:
                                    _LOGGER.debug(
                                        "Linked switch %s changed, updating %s",
                                        dp_address,
                                        self.entity_id,
                                    )
                                    self.async_write_ha_state()

                                return _callback

                            callback_func = make_callback(peer_address)
                            data_point.register_update_callback(callback_func)
                            self._linked_switch_callbacks[peer_address] = callback_func

                            _LOGGER.debug(
                                "Registered linked switch %s for %s",
                                peer_address,
                                self.entity_id,
                            )
                            break

                except Exception as err:
                    _LOGGER.debug(
                        "Error processing peer %s for %s: %s",
                        peer_address,
                        self.entity_id,
                        err,
                    )

            if self._linked_switches:
                _LOGGER.info(
                    "Found %d linked switches for %s: %s",
                    len(self._linked_switches),
                    self.entity_id,
                    list(self._linked_switches.keys()),
                )
                self.async_write_ha_state()

        except Exception as err:
            _LOGGER.error(
                "Error discovering linked switches for %s: %s",
                self.entity_id,
                err,
            )

    def _unregister_linked_switch_callbacks(self) -> None:
        """Unregister all linked switch callbacks."""
        for peer_address, callback_func in self._linked_switch_callbacks.items():
            try:
                data_point = self._linked_switches.get(peer_address)
                if data_point:
                    data_point.unregister_update_callback(callback_func)
            except Exception as err:
                _LOGGER.debug(
                    "Error unregistering callback for %s: %s",
                    peer_address,
                    err,
                )
        self._linked_switch_callbacks = {}

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the hvac action based on linked switches or fallback to activity."""
        # If thermostat mode is OFF, return OFF
        if self._data_point.mode == ClimateMode.OFF:
            return HVACAction.OFF

        # If we have linked switches, use their state
        if self._linked_switches:
            # Check if any linked switch is ON
            for data_point in self._linked_switches.values():
                try:
                    if hasattr(data_point, "value") and data_point.value is True:
                        return HVACAction.HEATING
                except Exception as err:
                    _LOGGER.debug("Error reading linked switch state: %s", err)

            # All linked switches are OFF
            return HVACAction.IDLE

        # Fallback to existing activity-based mapping
        if self._data_point.activity and self._data_point.activity in HM_TO_HA_ACTION:
            return HM_TO_HA_ACTION[self._data_point.activity]

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes including linked switch diagnostics."""
        attributes = super().extra_state_attributes

        # Add diagnostic attributes
        if self._linked_switches:
            attributes["using_linked_switches"] = True
            attributes["linked_switches"] = list(self._linked_switches.keys())

            # Add switch states
            linked_switch_states = {}
            for address, data_point in self._linked_switches.items():
                try:
                    if hasattr(data_point, "value"):
                        linked_switch_states[address] = data_point.value
                except Exception as err:
                    _LOGGER.debug("Error reading state for %s: %s", address, err)
                    linked_switch_states[address] = None

            attributes["linked_switch_states"] = linked_switch_states
        else:
            attributes["using_linked_switches"] = False

        return attributes
