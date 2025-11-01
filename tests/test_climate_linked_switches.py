"""Unit tests for climate linked switches feature."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from custom_components.homematicip_local.climate_extended import AioHomematicClimateWithLinkedSwitches
from homeassistant.components.climate import HVACAction
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_climate_data_point():
    """Create a mock climate data point."""
    data_point = Mock()
    data_point.unique_id = "test_climate_unique_id"
    data_point.enabled_default = True
    data_point.parameter = "SET_TEMPERATURE"
    data_point.mode = MagicMock()
    data_point.activity = None
    data_point.target_temperature_step = 0.5
    data_point.min_temp = 5.0
    data_point.max_temp = 30.0
    data_point.is_valid = True
    data_point.target_temperature = 21.0
    data_point.current_temperature = 20.0
    data_point.current_humidity = None
    data_point.modes = []
    data_point.profiles = []
    data_point.supports_profiles = False

    # Mock device and channel
    mock_channel = Mock()
    mock_channel.address = "TEST123:1"
    mock_channel.is_in_multi_group = False
    mock_channel.group_master = None
    data_point.channel = mock_channel

    mock_device = Mock()
    mock_device.identifier = "TEST123"
    mock_device.room = None
    mock_device.has_sub_devices = False
    
    # Mock central
    mock_central = Mock()
    mock_central.name = "test_central"
    mock_device.central = mock_central
    
    # Mock client with get_link_peers
    mock_client = AsyncMock()
    mock_client.get_link_peers = AsyncMock(return_value=[])
    mock_device.client = mock_client
    
    data_point.device = mock_device

    return data_point


@pytest.fixture
def mock_control_unit():
    """Create a mock control unit."""
    control_unit = Mock()
    control_unit.enable_sub_devices = False
    return control_unit


@pytest.mark.asyncio
async def test_climate_extended_init(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test initialization of extended climate entity."""
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    assert entity is not None
    assert entity._linked_switches == {}
    assert entity._linked_switch_callbacks == {}


@pytest.mark.asyncio
async def test_climate_extended_no_linked_switches(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test climate entity with no linked switches."""
    # Setup mock to return empty list of peers
    mock_climate_data_point.device.client.get_link_peers.return_value = []
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    assert len(entity._linked_switches) == 0
    assert entity.extra_state_attributes["using_linked_switches"] is False


@pytest.mark.asyncio
async def test_climate_extended_with_linked_switches(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test climate entity discovering linked switches."""
    # Create mock linked switch data point
    mock_switch_dp = Mock()
    mock_switch_dp.parameter = "STATE"
    mock_switch_dp.value = False
    mock_switch_dp.register_update_callback = Mock()
    mock_switch_dp.unregister_update_callback = Mock()
    
    # Create mock peer channel
    mock_peer_channel = Mock()
    mock_peer_channel.data_points = {"STATE": mock_switch_dp}
    
    # Create mock peer device
    mock_peer_device = Mock()
    mock_peer_device.get_channel = Mock(return_value=mock_peer_channel)
    
    # Setup central to return peer device
    mock_climate_data_point.device.central.get_device = Mock(return_value=mock_peer_device)
    
    # Setup client to return peer addresses
    mock_climate_data_point.device.client.get_link_peers.return_value = ["SWITCH123:3"]
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    # Verify linked switch was discovered
    assert len(entity._linked_switches) == 1
    assert "SWITCH123:3" in entity._linked_switches
    assert entity._linked_switches["SWITCH123:3"] == mock_switch_dp
    
    # Verify callback was registered
    assert mock_switch_dp.register_update_callback.called
    
    # Verify extra state attributes
    attrs = entity.extra_state_attributes
    assert attrs["using_linked_switches"] is True
    assert "SWITCH123:3" in attrs["linked_switches"]
    assert attrs["linked_switch_states"]["SWITCH123:3"] is False


@pytest.mark.asyncio
async def test_hvac_action_with_linked_switch_on(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test HVAC action when linked switch is ON."""
    from aiohomematic.model.custom import ClimateMode
    
    # Create mock linked switch data point (ON)
    mock_switch_dp = Mock()
    mock_switch_dp.parameter = "STATE"
    mock_switch_dp.value = True
    mock_switch_dp.register_update_callback = Mock()
    
    # Create mock peer channel
    mock_peer_channel = Mock()
    mock_peer_channel.data_points = {"STATE": mock_switch_dp}
    
    # Create mock peer device
    mock_peer_device = Mock()
    mock_peer_device.get_channel = Mock(return_value=mock_peer_channel)
    
    # Setup central to return peer device
    mock_climate_data_point.device.central.get_device = Mock(return_value=mock_peer_device)
    
    # Setup client to return peer addresses
    mock_climate_data_point.device.client.get_link_peers.return_value = ["SWITCH123:3"]
    
    # Set climate mode to AUTO (not OFF)
    mock_climate_data_point.mode = ClimateMode.AUTO
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    # Verify HVAC action is HEATING when switch is ON
    assert entity.hvac_action == HVACAction.HEATING


@pytest.mark.asyncio
async def test_hvac_action_with_linked_switch_off(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test HVAC action when linked switch is OFF."""
    from aiohomematic.model.custom import ClimateMode
    
    # Create mock linked switch data point (OFF)
    mock_switch_dp = Mock()
    mock_switch_dp.parameter = "STATE"
    mock_switch_dp.value = False
    mock_switch_dp.register_update_callback = Mock()
    
    # Create mock peer channel
    mock_peer_channel = Mock()
    mock_peer_channel.data_points = {"STATE": mock_switch_dp}
    
    # Create mock peer device
    mock_peer_device = Mock()
    mock_peer_device.get_channel = Mock(return_value=mock_peer_channel)
    
    # Setup central to return peer device
    mock_climate_data_point.device.central.get_device = Mock(return_value=mock_peer_device)
    
    # Setup client to return peer addresses
    mock_climate_data_point.device.client.get_link_peers.return_value = ["SWITCH123:3"]
    
    # Set climate mode to AUTO (not OFF)
    mock_climate_data_point.mode = ClimateMode.AUTO
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    # Verify HVAC action is IDLE when switch is OFF
    assert entity.hvac_action == HVACAction.IDLE


@pytest.mark.asyncio
async def test_hvac_action_mode_off(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test HVAC action returns OFF when thermostat mode is OFF."""
    from aiohomematic.model.custom import ClimateMode
    
    # Set climate mode to OFF
    mock_climate_data_point.mode = ClimateMode.OFF
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    # Verify HVAC action is OFF regardless of linked switches
    assert entity.hvac_action == HVACAction.OFF


@pytest.mark.asyncio
async def test_hvac_action_fallback_to_activity(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test HVAC action falls back to activity when no linked switches."""
    from aiohomematic.model.custom import ClimateActivity, ClimateMode
    
    # Set climate mode to AUTO
    mock_climate_data_point.mode = ClimateMode.AUTO
    
    # Set activity
    mock_climate_data_point.activity = ClimateActivity.HEAT
    
    # No linked switches
    mock_climate_data_point.device.client.get_link_peers.return_value = []
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    # Verify HVAC action falls back to activity-based mapping
    assert entity.hvac_action == HVACAction.HEATING


@pytest.mark.asyncio
async def test_manual_reload(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test manual reload of linked switches."""
    # Initially no peers
    mock_climate_data_point.device.client.get_link_peers.return_value = []
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    assert len(entity._linked_switches) == 0
    
    # Now add a peer
    mock_switch_dp = Mock()
    mock_switch_dp.parameter = "STATE"
    mock_switch_dp.value = False
    mock_switch_dp.register_update_callback = Mock()
    mock_switch_dp.unregister_update_callback = Mock()
    
    mock_peer_channel = Mock()
    mock_peer_channel.data_points = {"STATE": mock_switch_dp}
    
    mock_peer_device = Mock()
    mock_peer_device.get_channel = Mock(return_value=mock_peer_channel)
    
    mock_climate_data_point.device.central.get_device = Mock(return_value=mock_peer_device)
    mock_climate_data_point.device.client.get_link_peers.return_value = ["SWITCH123:3"]
    
    # Reload
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    # Verify linked switch was discovered after reload
    assert len(entity._linked_switches) == 1
    assert "SWITCH123:3" in entity._linked_switches


@pytest.mark.asyncio
async def test_callback_unregistration(
    hass: HomeAssistant,
    mock_control_unit: Mock,
    mock_climate_data_point: Mock,
) -> None:
    """Test callbacks are unregistered properly."""
    # Create mock linked switch data point
    mock_switch_dp = Mock()
    mock_switch_dp.parameter = "STATE"
    mock_switch_dp.value = False
    mock_switch_dp.register_update_callback = Mock()
    mock_switch_dp.unregister_update_callback = Mock()
    
    # Create mock peer channel
    mock_peer_channel = Mock()
    mock_peer_channel.data_points = {"STATE": mock_switch_dp}
    
    # Create mock peer device
    mock_peer_device = Mock()
    mock_peer_device.get_channel = Mock(return_value=mock_peer_channel)
    
    # Setup central to return peer device
    mock_climate_data_point.device.central.get_device = Mock(return_value=mock_peer_device)
    
    # Setup client to return peer addresses
    mock_climate_data_point.device.client.get_link_peers.return_value = ["SWITCH123:3"]
    
    entity = AioHomematicClimateWithLinkedSwitches(
        control_unit=mock_control_unit,
        data_point=mock_climate_data_point,
    )
    
    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_reload_linked_switches()
    
    # Verify callback was registered
    assert mock_switch_dp.register_update_callback.called
    
    # Unregister callbacks
    entity._unregister_linked_switch_callbacks()
    
    # Verify callback was unregistered
    assert mock_switch_dp.unregister_update_callback.called
    assert len(entity._linked_switch_callbacks) == 0
