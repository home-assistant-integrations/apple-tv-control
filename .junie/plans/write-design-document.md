---
sessionId: session-261116-204959-1fmb
---

# Overview

### ✓ Step 1: Create directory structure and write the design document

### Purpose
Create a comprehensive Software Design and Implementation Plan document at `docs/dev/DESIGN_AND_IMPLEMENTATION.md` for the `apple-tv-control` project — a Home Assistant custom integration for controlling Apple TV devices.

### Current State
The project is a greenfield skeleton:
- `README.md` describes the integration's purpose and features
- `main.py` is a PyCharm template placeholder
- `pyproject.toml` has basic Python 3.13+ config with no dependencies
- No `docs/` directory exists yet

### Document Scope
The document will cover a **full greenfield design** for a **Home Assistant custom integration** including **all listed features**:
- Power on/off
- Navigate up, down, left, right
- Select
- Back (normal + long press)
- TV (normal + long press)
- Play/Pause
- Mute/Unmute
- Volume up/down

### Key Technical Context
- **Framework**: Home Assistant custom integration (installed via HACS)
- **Library**: pyatv for Apple TV communication (scan, pair, connect, control)
- **Entity Type**: `media_player` platform with `device_class: tv`
- **Pattern**: Config flow for UI-based setup, coordinator for connection management
- **pyatv APIs**: `RemoteControl` for navigation/media, `Power` for power management, `InputAction` for long-press support

---

## Implementation Phases

### ✓ Phase 1: Project Scaffolding

**Goal:** Establish the integration skeleton with proper metadata.

**Files Created:**
- `custom_components/apple_tv_control/__init__.py` — Integration entry point with stub setup/unload functions
- `custom_components/apple_tv_control/manifest.json` — Integration metadata (domain, version, pyatv dependency)
- `custom_components/apple_tv_control/const.py` — Domain name, platform list, default values
- `custom_components/apple_tv_control/hacs.json` — HACS metadata
- `custom_components/apple_tv_control/strings.json` — Config flow localization strings

**Definition of Done:** Integration skeleton is in place and ready for Phase 2 (Config Flow).

### ✓ Phase 2: Config Flow

**Goal:** UI-based device discovery and pairing.

**Files Created:**
- `custom_components/apple_tv_control/config_flow.py` — Config flow with discovery, pairing, and reauth

**Definition of Done:** User can add the integration via UI, select a device, complete pairing, and see a config entry.

### ✓ Phase 3: Connection Coordinator

**Goal:** Reliable connection management with reconnection logic.

**Files Created/Modified:**
- `custom_components/apple_tv_control/coordinator.py` — DataUpdateCoordinator subclass with connect/disconnect, push updates, polling, and reconnection
- `custom_components/apple_tv_control/__init__.py` — Coordinator setup in hass.data and cleanup on unload

**Definition of Done:** Coordinator connects to a real or mocked Apple TV, reports power state, and reconnects on disconnect.

### ✓ Phase 4: Media Player Entity — Core Controls

**Goal:** Power, play/pause, and volume controls via the media player entity.

**Files Created/Modified:**
- `custom_components/apple_tv_control/media_player.py` — MediaPlayerEntity with power, playback, volume, and media metadata
- `custom_components/apple_tv_control/coordinator.py` — Fixed `power_state` to use property, `playing()` to use async method

**Definition of Done:** Media player entity appears in Home Assistant with power, play/pause, and volume controls working.

### ✓ Phase 5: Navigation Controls

**Goal:** Directional navigation and select via custom services.

**Files Created/Modified:**
- `custom_components/apple_tv_control/services.yaml` — Service definitions for navigate, select, and back
- `custom_components/apple_tv_control/__init__.py` — Service registration and handlers

**Definition of Done:** User can call navigate, select, and back services from automations or the developer console.

### ✓ Phase 6: Advanced Controls — Long Press

**Goal:** Long-press actions for Back and TV buttons via button entities.

**Files Created/Modified:**
- `custom_components/apple_tv_control/button.py` — Two ButtonEntity classes for Back long press and TV long press using `InputAction.Hold`

**Definition of Done:** Two button entities appear in Home Assistant for long-press actions, callable from automations.

### ✓ Phase 7: HACS Packaging and Documentation

**Goal:** Package the integration for distribution via HACS with proper CI, licensing, and user documentation.

**Files Created/Modified:**
- `.gitignore` — Exclude `.venv`, `__pycache__`, IDE files, etc.
- `LICENSE` — MIT license
- `.github/workflows/validate.yml` — CI with hassfest and ruff linting
- `custom_components/apple_tv_control/hacs.json` — Added version and minimum Home Assistant version
- `custom_components/apple_tv_control/manifest.json` — Added codeowners
- `README.md` — Full installation instructions, entity docs, service examples, troubleshooting

**Definition of Done:** Integration is properly packaged for HACS distribution with CI validation, license, and user-facing documentation.