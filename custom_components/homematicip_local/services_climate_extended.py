"""Services for extended climate platform with linked switches."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import DOMAIN, HmipLocalServices

_LOGGER = logging.getLogger(__name__)


def async_register_climate_extended_services(hass: HomeAssistant) -> None:
    """Register services for climate entities with linked switches."""
    
    # Register the reload_linked_switches service
    async_register_platform_entity_service(
        hass=hass,
        service_domain=DOMAIN,
        service_name=HmipLocalServices.RELOAD_LINKED_SWITCHES,
        entity_domain="climate",
        schema={},
        func="async_reload_linked_switches",
    )
    
    _LOGGER.debug("Registered climate extended services")
