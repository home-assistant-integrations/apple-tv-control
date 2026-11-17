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
