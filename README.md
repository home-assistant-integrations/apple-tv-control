# Apple TV Control

[![Open your Home Assistant instance and search for Apple TV Control](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=home-assistant-integrations&repository=apple-tv-control)

A Home Assistant custom integration for comprehensive Apple TV remote control. Unlike the default Home Assistant Apple TV integration, which focuses on metadata and playback state, this integration prioritizes **device control** — navigation, media playback, power management, and advanced button actions (long press).

Built on [pyatv](https://pyatv.dev) for Apple TV communication.

## Features

| Category | Controls |
|----------|----------|
| **Power** | Turn on, turn off |
| **Navigation** | Up, down, left, right, select |
| **Media** | Play, pause, stop, next track, previous track |
| **Volume** | Volume up, volume down, mute/unmute |
| **Back** | Normal press, long press |
| **TV (Home)** | Normal press, long press |

## Prerequisites

- Home Assistant ≥ 2024.1.0
- Apple TV (4th generation or later recommended)
- [HACS](https://hacs.xyz/) (Home Assistant Community Store)

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Search for **Apple TV Control**
3. Click **Download**
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/apple_tv_control` directory to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Apple TV Control**
3. Select your Apple TV from the discovered devices (or enter the IP address manually)
4. Complete the pairing process by entering the PIN code displayed on your Apple TV
5. The integration will create a media player entity and button entities for your Apple TV

## Entities Created

| Entity | Type | Description |
|--------|------|-------------|
| `media_player.{name}` | Media Player | Main control entity with power, playback, and volume |
| `button.{name}_back_long_press` | Button | Long-press the Back (Menu) button |
| `button.{name}_tv_long_press` | Button | Long-press the TV (Home) button |

## Custom Services

The integration provides custom services for navigation and button actions.

### Navigate

Send a directional navigation command:

```yaml
service: apple_tv_control.navigate
data:
  entity_id: media_player.living_room_apple_tv
  direction: "up"  # up, down, left, right
```

### Select

Press the select (center) button:

```yaml
service: apple_tv_control.select
data:
  entity_id: media_player.living_room_apple_tv
```

### Back

Press the back (menu) button:

```yaml
service: apple_tv_control.back
data:
  entity_id: media_player.living_room_apple_tv
```

## Usage Examples

### Automation: Turn on Apple TV and open Netflix

```yaml
automation:
  trigger:
    - platform: state
      entity_id: input_boolean.watch_tv
      to: "on"
  action:
    - service: switch.turn_on
      target:
        entity_id: switch.apple_tv_power
    - delay: "00:00:05"
    - service: apple_tv_control.select
      data:
        entity_id: media_player.living_room_apple_tv
```

### Script: Navigate to a menu item

```yaml
script:
  settings_menu:
    sequence:
      - service: apple_tv_control.navigate
        data:
          entity_id: media_player.living_room_apple_tv
          direction: "down"
      - delay: "00:00:01"
      - service: apple_tv_control.navigate
        data:
          entity_id: media_player.living_room_apple_tv
          direction: "down"
      - delay: "00:00:01"
      - service: apple_tv_control.select
        data:
          entity_id: media_player.living_room_apple_tv
```

## Known Limitations

- **Deep Sleep**: When Apple TV enters deep sleep (low-power mode), it becomes unreachable. The integration will mark entities as unavailable and attempt to reconnect when the device wakes.
- **Power On from Deep Sleep**: If the Apple TV is in deep sleep, power-on may require a Wake-on-LAN packet (not yet supported). Using a smart plug as a fallback is recommended.
- **Companion Protocol**: Enhanced power management requires Companion protocol pairing. If pairing fails, the integration falls back to MRP-only mode.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Device not discovered | Ensure Apple TV and Home Assistant are on the same network; try manual IP entry |
| Pairing fails | Restart the pairing process from the integration options; ensure you enter the PIN promptly |
| Entities show unavailable | Check that the Apple TV is powered on and reachable; check Home Assistant logs for connection errors |
| Commands not working | Verify the entity is available (not unavailable); check logs for pyatv errors |

## Development

This integration follows the [Home Assistant custom integration guidelines](https://developers.home-assistant.io/docs/api_lib_index).

- **pyatv documentation**: https://pyatv.dev
- **pyatv GitHub**: https://github.com/postlund/pyatv
- **Design document**: [docs/dev/DESIGN_AND_IMPLEMENTATION.md](docs/dev/DESIGN_AND_IMPLEMENTATION.md)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
