# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows the calendar-based pattern **yyyy.mm.rm**, where:
- **yyyy** = year
- **mm** = month
- **rm** = release of the month, starting at 0 and incrementing (0, 1, 2, ...) for each release; resets to 0 when the month changes

## [Unreleased]

### Fixed

- Play did not resume paused media in apps that ignore the play command (e.g. waipu.tv); play now resumes paused media by pressing the remote's play/pause button, like the Siri Remote, and the play/pause action presses that button too

## [2026.11.5] - 2026-11-18

### Added

- **README**: Update button next to the install button; it opens the update overview of Home Assistant
- **README**: Troubleshooting entry for new releases that do not show up as updates (HACS checks custom repositories only every 48 hours)

### Changed

- **Release workflow**: Moves the `[Unreleased]` entries into the new version's section (used as release notes), sets the version in `manifest.json` and `const.py` on the release branch, refuses to release without changelog entries, and fast-forwards `main` to the release afterwards

## [2026.11.4] - 2026-11-17

### Added

- **Remote buttons**: Up, Down, Left, Right, Select, Back (Menu) and TV (Home), shown on the device page and as device actions in automations
- **Icons**: Integration icon (light and dark theme, shown by Home Assistant 2026.3 and later) and an icon for every remote button; the media player is a TV

### Fixed

- Mute did nothing or timed out: it now works when the audio output has a volume level (HomePod, AirPlay speakers) and is not offered when the Apple TV only has volume up/down (TV volume over HDMI-CEC)

### Changed

- Code owner is `@thbonk`

## [2026.11.3] - 2026-11-17

### Fixed

- Config flow failed with "Invalid handler specified": imports of names pyatv does not have (`PyatvError`, `PowerState` from `pyatv.interface`)
- Pairing only tried MRP, which current tvOS no longer pairs; it now pairs every protocol the Apple TV requires (AirPlay and Companion on current tvOS), and a wrong PIN shows an error instead of aborting
- Setup failed after pairing (polling interval not a `timedelta`, push updater started with `await`), and push updates and reconnects never ran because the listener methods did not match pyatv
- Media player crashed when disconnected and on every state update (non-existent `MediaPlayerState.UNAVAILABLE` and `PLAY_PAUSE` feature); seek, app name and position time now work
- Button names repeated the device name; entities now update from pushed state
- Zeroconf discovery matched every HomeKit and AirPlay device and created duplicate flows; it now matches Apple TVs only and asks for confirmation
- Rejected credentials now start re-authentication, which updates the existing entry
- Options flow crashed when opened; the name option now renames the device
- Services crashed on Home Assistant before 2025.10
- Added `translations/en.json`, which custom integrations need for their UI texts

### Changed

- Requires Home Assistant ≥ 2024.12.0

## [2026.11.2] - 2026-11-17

### Fixed

- README install button: HACS reported "Repository not found" because the link had no `category`; the install steps now add the repository as a custom repository

## [2026.11.1] - 2026-11-17

### Fixed

- README install button pointed to the wrong repository owner

## [2026.11.0] - 2026-11-17

### Added

- **Project scaffolding**: Integration entry point, manifest, constants, HACS metadata, and localization strings
- **Config flow**: UI-based device discovery (manual IP entry and zeroconf auto-discovery), MRP/Companion pairing with PIN entry, reauth flow, and options flow for friendly name override
- **Connection coordinator**: Reliable connection management with push updates, polling fallback (30s interval), and exponential backoff reconnection (max 3 attempts)
- **Media player entity**: Core controls including power on/off, play/pause/stop, volume up/down/mute, next/previous track, and media seeking; media metadata display (title, artist, album, duration, position, app name)
- **Navigation services**: Custom Home Assistant services for directional navigation (`apple_tv_control.navigate`), select (`apple_tv_control.select`), and back (`apple_tv_control.back`)
- **Button entities**: Long-press actions for Back (Menu) and TV (Home) buttons via `button` platform
- **HACS packaging**: `.gitignore`, MIT license, CI workflow (hassfest + ruff linting), and updated `hacs.json` with version and minimum Home Assistant version
- **Documentation**: Full `README.md` with installation instructions, entity table, service examples, automation/script usage, known limitations, and troubleshooting guide
- **Design document**: Comprehensive software design and implementation plan at `docs/dev/DESIGN_AND_IMPLEMENTATION.md`

### Notes

- Requires Home Assistant ≥ 2024.1.0 and pyatv ≥ 0.18.0
- Apple TV 4th generation or later recommended
- Companion protocol pairing is optional; integration falls back to MRP-only if pairing fails
- This is the initial release
