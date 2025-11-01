# Linked Switch Support for Climate Entities

## Overview

This feature allows climate entities (such as HmIP-STHD thermostats) to determine their `hvac_action` based on the state of parameter-linked switches (such as HmIP-FAL230-C10 switch actuators). This provides more accurate heating/cooling status when the thermostat controls heating through linked switches.

## How It Works

When enabled, climate entities:

1. **Automatically discover linked switches** during initialization by querying parameter links via `device.client.get_link_peers()`
2. **Monitor switch states** by registering callbacks on linked DpSwitch data points (parameter 'STATE')
3. **Determine hvac_action** based on actual switch states:
   - `OFF` if HVAC mode is OFF
   - `HEATING` if any linked switch is ON
   - `IDLE` if all linked switches are OFF
   - Falls back to activity-based detection if no linked switches are found

## Activation

### Configuration Entry Options

Add the `enable_climate_linked_switches` option to your config entry:

```yaml
# configuration.yaml
homematicip_local:
  - instance_name: "My Home"
    host: "192.168.1.100"
    # ... other options ...
    enable_climate_linked_switches: true
```

Or set it via the integration's configuration options in the UI.

### Checking Configuration

You can verify the feature is active by checking the climate entity's extra state attributes:

- `using_linked_switches`: Boolean indicating if linked switches are being used
- `linked_switches`: List of linked switch addresses
- `linked_switch_states`: Dictionary of switch addresses and their current states

## Services

### `homematicip_local.reload_linked_switches`

Manually reload the linked switches for a climate entity. Useful if device links have changed.

**Example:**

```yaml
service: homematicip_local.reload_linked_switches
target:
  entity_id: climate.living_room_thermostat
```

## Debugging

### Logging

Enable debug logging to see detailed information about linked switch discovery and state changes:

```yaml
logger:
  logs:
    custom_components.homematicip_local.climate_extended: debug
```

### Diagnostic Attributes

Check the climate entity's state attributes in Developer Tools > States to see:

- Which switches are linked
- Current state of each linked switch
- Whether the feature is active

### Common Issues

1. **No linked switches found**
   - Ensure switches are properly linked in the CCU/backend
   - Check that the switch supports the STATE parameter
   - Verify the device is reachable

2. **Incorrect hvac_action**
   - Check switch states in diagnostic attributes
   - Verify HVAC mode is not OFF
   - Check debug logs for callback registrations

3. **Switches not updating**
   - Use the `reload_linked_switches` service
   - Check device connectivity
   - Verify callbacks are registered (check debug logs)

## Implementation Details

### Class: `AioHomematicClimateWithLinkedSwitches`

Extends `AioHomematicClimate` with linked switch support.

**Key Methods:**

- `async_added_to_hass()`: Loads linked switches on entity initialization
- `async_reload_linked_switches()`: Manually reload linked switches
- `hvac_action`: Overridden to consider linked switch states
- `extra_state_attributes`: Enhanced with diagnostic information
- `async_will_remove_from_hass()`: Cleans up callbacks

### Link Discovery Process

1. Get the climate entity's channel address
2. Query `device.client.get_link_peers(address=channel_address)`
3. For each peer address:
   - Get the peer device from central
   - Get the peer channel
   - Find DpSwitch data points with parameter 'STATE'
   - Register update callback
   - Store initial state

### State Management

- `_linked_switches`: Dict of peer_address -> DpSwitch
- `_linked_switch_states`: Dict of peer_address -> bool
- `_switch_callbacks`: Dict of peer_address -> callback_function

## Testing

The feature includes comprehensive unit tests in `tests/test_climate_linked_switches.py`:

- Loading linked switches with and without peers
- hvac_action behavior in different modes
- Extra state attributes
- Manual reload functionality
- Callback registration and cleanup

Run tests with:

```bash
pytest tests/test_climate_linked_switches.py -v
```

## Example Use Case

A living room has:
- HmIP-STHD thermostat controlling the room temperature
- HmIP-FAL230-C10 switch actuator controlling the floor heating relay

By linking the thermostat to the switch in the CCU and enabling this feature:
1. The thermostat sends commands to the switch based on temperature
2. The climate entity monitors the switch state
3. `hvac_action` accurately reflects `HEATING` when the switch is ON
4. Home Assistant automations can trigger on actual heating status

## Compatibility

- **Devices**: Works with any Homematic IP climate device that supports parameter links
- **Switches**: Requires DpSwitch devices with STATE parameter
- **Backend**: Compatible with CCU2, CCU3, RaspberryMatic, and other Homematic backends

## Future Enhancements

Potential improvements:
- Support for cooling mode (linked cooling switches)
- Multi-stage heating/cooling support
- Configurable switch parameter names
- UI configuration for link discovery
