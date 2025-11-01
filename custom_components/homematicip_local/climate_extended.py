"""Extended climate platform for Homematic(IP) Local with linked switch support."""

from __future__ import annotations

import logging
from typing import Any

from aiohomematic.const import CALLBACK_TYPE
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.model.generic import DpSwitch
from homeassistant.components.climate import HVACAction
from homeassistant.core import callback

from .climate import AioHomematicClimate
from .control_unit import ControlUnit

_LOGGER = logging.getLogger(__name__)


class AioHomematicClimateWithLinkedSwitches(AioHomematicClimate):
    """Climate entity that determines hvac_action based on linked switches."""

    def __init__(
        self,
        control_unit: ControlUnit,
        data_point,
    ) -> None:
        """Initialize the extended climate entity."""
        super().__init__(control_unit=control_unit, data_point=data_point)
        self._linked_switches: dict[str, DpSwitch] = {}
        self._linked_switch_states: dict[str, bool] = {}
        self._switch_callbacks: dict[str, CALLBACK_TYPE] = {}

    async def async_added_to_hass(self) -> None:
        """Register entity and load linked switches."""
        await super().async_added_to_hass()
        await self._async_load_linked_switches()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks before removal."""
        await self._async_unregister_switch_callbacks()
        await super().async_will_remove_from_hass()

    async def _async_load_linked_switches(self) -> None:
        """Load parameter-linked switches via device.client.get_link_peers."""
        try:
            # Get the channel address for this climate entity
            channel_address = self._data_point.channel.address

            # Get linked peers for this channel
            device = self._data_point.device
            linked_peers = await device.client.get_link_peers(address=channel_address)

            if not linked_peers:
                _LOGGER.debug(
                    "No linked peers found for climate entity %s at %s",
                    self.name,
                    channel_address,
                )
                return

            # Find DpSwitch data points on linked channels
            for peer_address in linked_peers:
                try:
                    # Get the device for this peer
                    peer_device_address = peer_address.split(":")[0]
                    peer_device = device.central.get_device(address=peer_device_address)

                    if not peer_device:
                        _LOGGER.debug("Peer device %s not found", peer_device_address)
                        continue

                    # Get the channel
                    peer_channel = peer_device.get_channel(address=peer_address)
                    if not peer_channel:
                        _LOGGER.debug("Peer channel %s not found", peer_address)
                        continue

                    # Find STATE parameter (typical for switches)
                    for data_point in peer_channel.data_points.values():
                        if isinstance(data_point, DpSwitch) and data_point.parameter == "STATE":
                            self._linked_switches[peer_address] = data_point
                            self._linked_switch_states[peer_address] = bool(data_point.value)
                            
                            # Register callback for state changes
                            callback_handler = self._create_switch_callback(peer_address)
                            data_point.register_callback(cb=callback_handler)
                            self._switch_callbacks[peer_address] = callback_handler
                            
                            _LOGGER.debug(
                                "Registered linked switch %s for climate entity %s",
                                peer_address,
                                self.name,
                            )
                            break

                except (IndexError, AttributeError, BaseHomematicException) as err:
                    _LOGGER.debug(
                        "Error processing linked peer %s: %s",
                        peer_address,
                        err,
                    )
                    continue

            if self._linked_switches:
                _LOGGER.info(
                    "Climate entity %s loaded %d linked switches",
                    self.name,
                    len(self._linked_switches),
                )

        except BaseHomematicException as err:
            _LOGGER.warning(
                "Failed to load linked switches for climate entity %s: %s",
                self.name,
                err,
            )

    def _create_switch_callback(self, peer_address: str) -> CALLBACK_TYPE:
        """Create a callback function for a specific switch."""
        @callback
        def _switch_state_changed(*args: Any, **kwargs: Any) -> None:
            """Handle switch state change."""
            if switch := self._linked_switches.get(peer_address):
                self._linked_switch_states[peer_address] = bool(switch.value)
                _LOGGER.debug(
                    "Switch %s state changed to %s for climate entity %s",
                    peer_address,
                    switch.value,
                    self.name,
                )
                # Trigger entity update
                self.async_write_ha_state()
        
        return _switch_state_changed

    async def _async_unregister_switch_callbacks(self) -> None:
        """Unregister all switch callbacks."""
        for peer_address, callback_handler in self._switch_callbacks.items():
            if switch := self._linked_switches.get(peer_address):
                try:
                    switch.unregister_callback(cb=callback_handler)
                    _LOGGER.debug(
                        "Unregistered callback for switch %s",
                        peer_address,
                    )
                except BaseHomematicException as err:
                    _LOGGER.debug(
                        "Error unregistering callback for switch %s: %s",
                        peer_address,
                        err,
                    )
        
        self._switch_callbacks.clear()
        self._linked_switches.clear()
        self._linked_switch_states.clear()

    async def async_reload_linked_switches(self) -> None:
        """Reload linked switches (for service call)."""
        _LOGGER.info("Reloading linked switches for climate entity %s", self.name)
        await self._async_unregister_switch_callbacks()
        await self._async_load_linked_switches()
        self.async_write_ha_state()

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the hvac action, considering linked switches."""
        # If we have linked switches, use their state to determine action
        if self._linked_switches:
            # If mode is OFF, action is OFF
            if self.hvac_mode and self.hvac_mode.value == "off":
                return HVACAction.OFF
            
            # If any linked switch is ON, we're heating
            if any(self._linked_switch_states.values()):
                return HVACAction.HEATING
            
            # If all linked switches are OFF, we're idle
            return HVACAction.IDLE
        
        # Fallback to existing activity-based mapping
        return super().hvac_action

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes with linked switch diagnostics."""
        attributes = super().extra_state_attributes
        
        # Add diagnostics about linked switches
        if self._linked_switches:
            attributes["linked_switches"] = list(self._linked_switches.keys())
            attributes["linked_switch_states"] = dict(self._linked_switch_states)
            attributes["using_linked_switches"] = True
        else:
            attributes["using_linked_switches"] = False
        
        return attributes
