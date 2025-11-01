# Linked Switches for Climate Entities

## Overview

This feature enables HomematicIP Local climate entities (e.g., HmIP-STHD thermostats) to determine their HVAC action state based on directly linked switches (e.g., HmIP-FAL230-C10 actuators). This is particularly useful when thermostats have direct parameter links to heating actuators, allowing Home Assistant to accurately reflect whether the heating system is actively heating, idle, or off.

## Motivation

In HomematicIP systems, thermostats can be directly linked to switches/actuators using parameter links. These links enable the thermostat to control the actuator based on temperature demands. Without this feature, the climate entity may not accurately report when heating is active, as it relies only on the thermostat's internal activity state, which may not reflect the actual actuator state.

With linked switch support, the climate entity:
- Queries parameter links to discover connected switches
- Monitors the STATE data point of linked switches
- Reports accurate HVAC action:
  - `OFF`: When thermostat mode is OFF
  - `HEATING`: When any linked switch is ON
  - `IDLE`: When all linked switches are OFF
  - Falls back to activity-based mapping if no linked switches are found

## Activation

The linked switches feature is **optional** and must be enabled in the integration options.

### Enable via Integration Options

1. Go to **Settings** → **Devices & Services**
2. Find your HomematicIP Local integration
3. Click **Configure**
4. Enable the option **Enable Climate Linked Switches**
5. Save the configuration
6. Reload the integration or restart Home Assistant

### Enable via Configuration Entry Data

Alternatively, you can enable it when setting up a new integration or by modifying the configuration entry data:

```yaml
# In your integration's data or options
enable_climate_linked_switches: true
```

## How It Works

### Discovery Process

When a climate entity with linked switches support is added to Home Assistant:

1. **Query Links**: The entity calls `device.client.get_link_peers(address=channel_address)` to get all linked channels
2. **Find Switches**: For each linked channel, it looks for `DpSwitch` data points with parameter `STATE`
3. **Register Callbacks**: Updates to linked switch states trigger an update of the climate entity's state
4. **Compute HVAC Action**: The `hvac_action` property checks linked switch states to determine heating activity

### HVAC Action Logic

```python
if thermostat_mode == OFF:
    return HVACAction.OFF
elif any_linked_switch_is_ON:
    return HVACAction.HEATING
elif all_linked_switches_are_OFF:
    return HVACAction.IDLE
else:
    # Fallback to activity-based mapping
    return activity_to_hvac_action(thermostat_activity)
```

## Services

### `reload_linked_switches`

Manually reload the discovery of linked switches for a climate entity. Useful if links are added or modified after the entity is created.

**Service Call Example:**

```yaml
service: homematicip_local.reload_linked_switches
target:
  entity_id: climate.thermostat_bedroom
```

**Usage:**
- Call this service after adding or removing parameter links in the CCU
- Useful for troubleshooting if linked switches are not detected initially

## Diagnostic Attributes

When linked switches are detected, the climate entity provides additional state attributes for debugging:

- **`using_linked_switches`** (bool): Whether linked switches are active for HVAC action determination
- **`linked_switches`** (list): List of linked channel addresses (e.g., `["SWITCH123:3", "SWITCH456:2"]`)
- **`linked_switch_states`** (dict): Current state of each linked switch (e.g., `{"SWITCH123:3": true, "SWITCH456:2": false}`)

**Example Attributes:**

```yaml
using_linked_switches: true
linked_switches:
  - "001A9D89ABC123:3"
linked_switch_states:
  "001A9D89ABC123:3": false
```

## Debugging & Troubleshooting

### Enable Debug Logging

Add the following to your `configuration.yaml` to see detailed logs:

```yaml
logger:
  default: info
  logs:
    custom_components.homematicip_local.climate_extended: debug
```

### Common Issues

1. **No linked switches discovered**
   - Verify that parameter links exist in your CCU between the thermostat and switch
   - Check that the switch has a `STATE` parameter
   - Call the `reload_linked_switches` service to re-discover links

2. **HVAC action not updating**
   - Check the `linked_switch_states` attribute to verify switch states are being read
   - Ensure the linked switches are reporting state changes
   - Review debug logs for errors during callback registration

3. **Feature not working after enabling**
   - Ensure you've reloaded the integration or restarted Home Assistant after enabling the option
   - Verify the climate entity is using the extended class (check logs for "Found X linked switches")

## Testing

### Unit Tests

The feature includes comprehensive unit tests:

```bash
pytest -k test_climate_linked_switches
```

Tests cover:
- Discovery of linked switches
- HVAC action behavior with switches ON/OFF
- Manual reload functionality
- Callback registration and unregistration
- Fallback to activity-based mapping
- Diagnostic attributes

### Manual Testing

1. Enable the feature in integration options
2. Reload the integration
3. Check climate entity attributes for `using_linked_switches: true`
4. Toggle a linked switch and verify HVAC action changes
5. Test the `reload_linked_switches` service

## Technical Notes

### Implementation Details

- **No aiohomematic Modifications**: All changes are in `homematicip_local` component
- **Lazy Import**: Extended class is imported only when feature is enabled
- **Callback Management**: Properly registers and unregisters callbacks to avoid memory leaks
- **Error Handling**: Robust error handling with logging for resilience
- **Backward Compatible**: Does not affect existing climate entities when disabled

### Files Modified/Created

- `custom_components/homematicip_local/const.py` - Added `CONF_ENABLE_CLIMATE_LINKED_SWITCHES` constant
- `custom_components/homematicip_local/climate.py` - Modified to conditionally use extended class
- `custom_components/homematicip_local/climate_extended.py` - New extended climate entity class
- `custom_components/homematicip_local/services.py` - Added service registration function
- `custom_components/homematicip_local/services.yaml` - Added `reload_linked_switches` service definition
- `tests/test_climate_linked_switches.py` - Comprehensive unit tests
- `docs/linked_switches.md` - This documentation

## Example Use Case

**Scenario**: You have a HmIP-STHD thermostat directly linked to a HmIP-FAL230-C10 switch actuator.

**Without this feature**:
- Climate entity shows HVAC action based on thermostat's internal activity
- May not accurately reflect when actuator is actually heating

**With this feature enabled**:
- Climate entity discovers the linked HmIP-FAL230-C10
- Monitors the switch STATE
- Reports `HEATING` when switch is ON, `IDLE` when OFF
- Provides accurate heating status in Home Assistant

## Support

If you encounter issues:
1. Enable debug logging
2. Check diagnostic attributes (`linked_switches`, `linked_switch_states`)
3. Verify parameter links exist in CCU
4. Use the `reload_linked_switches` service to refresh discovery
5. Review unit tests for expected behavior

For bugs or feature requests, please open an issue on the GitHub repository.
