# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows the calendar-based pattern **yyyy.mm.rm**, where:
- **yyyy** = year
- **mm** = month
- **rm** = release of the month, starting at 0 and incrementing (0, 1, 2, ...) for each release; resets to 0 when the month changes

## [Unreleased]

## [2026.11.0] - 2026-11-17

### Added

- **Project scaffolding**: Integration entry point, manifest, constants, HACS metadata, and localization strings
- **Config flow**: UI-based device discovery (manual IP entry and zeroconf auto-discovery), PIN pairing of every protocol the Apple TV requires (AirPlay and Companion on current tvOS), reauth flow, and options flow for friendly name override
- **Connection coordinator**: Reliable connection management with push updates, polling fallback (30s interval), and exponential backoff reconnection (max 3 attempts)
- **Media player entity**: Core controls including power on/off, play/pause/stop, volume up/down/mute, next/previous track, and media seeking; media metadata display (title, artist, album, duration, position, app name)
- **Navigation services**: Custom Home Assistant services for directional navigation (`apple_tv_control.navigate`), select (`apple_tv_control.select`), and back (`apple_tv_control.back`)
- **Button entities**: Remote buttons Up, Down, Left, Right, Select, Back (Menu) and TV (Home), plus long presses of Back and TV, shown on the device page and as device actions in automations
- **Icons**: Integration icon (light and dark theme, shown by Home Assistant 2026.3 and later) and an icon for every remote button; the media player is a TV
- **HACS packaging**: `.gitignore`, MIT license, CI workflow (hassfest + ruff linting), and updated `hacs.json` with version and minimum Home Assistant version
- **Documentation**: Full `README.md` with installation instructions, entity table, service examples, automation/script usage, known limitations, and troubleshooting guide
- **Design document**: Comprehensive software design and implementation plan at `docs/dev/DESIGN_AND_IMPLEMENTATION.md`

### Fixed

Fixes for installs taken from `main` before this release:

- Config flow failed with "Invalid handler specified": imports of names pyatv does not have (`PyatvError`, `PowerState` from `pyatv.interface`)
- Pairing only tried MRP, which current tvOS no longer pairs; wrong PINs now show an error instead of aborting
- Setup failed after pairing (polling interval not a `timedelta`, push updater started with `await`), and push updates and reconnects never ran because the listener methods did not match pyatv
- Media player crashed when disconnected and on every state update (non-existent `MediaPlayerState.UNAVAILABLE` and `PLAY_PAUSE` feature); seek, app name and position time now work
- Mute did nothing or timed out: it now works when the audio output has a volume level (HomePod, AirPlay speakers) and is not offered when the Apple TV only has volume up/down (TV over HDMI-CEC)
- Button names repeated the device name; entities now update from pushed state
- Zeroconf discovery matched every HomeKit and AirPlay device and created duplicate flows; it now matches Apple TVs only and asks for confirmation
- Rejected credentials now start re-authentication, which updates the existing entry
- Options flow crashed when opened; the name option now renames the device
- Services crashed on Home Assistant before 2025.10
- Added `translations/en.json`, which custom integrations need for their UI texts

### Notes

- Requires Home Assistant ≥ 2024.12.0 and pyatv ≥ 0.18.0
- Apple TV 4th generation or later recommended
- This is the initial release
