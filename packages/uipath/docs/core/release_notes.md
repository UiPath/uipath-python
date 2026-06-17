---
title: Release Notes
---

# Release Notes

A catalog of the releases most relevant to UiPath Python SDK users (breaking changes and notable updates). Full details live in each GitHub release, linked below.

## `uipath` (SDK & CLI)

| Release | Date | What's relevant | Notes |
|---------|------|-----------------|-------|
| [v2.10.0](https://github.com/UiPath/uipath-python/releases/tag/v2.10.0) | 2026-02-27 | Coded function schema `type` changed from `"agent"` to `"function"` | 🚨 Breaking |
| [v2.9.0](https://github.com/UiPath/uipath-python/releases/tag/v2.9.0) | 2026-02-23 | `platform` extracted to `uipath-platform`, context grounding contract changes, `uipath dev` defaults to `web` | 🚨 Breaking |
| [v2.2.0](https://github.com/UiPath/uipath-python/releases/tag/v2.2.0) | 2025-11-26 | Python 3.11+ required, `UiPath` import moved to `uipath.platform`, configuration architecture redesign | 🚨 Breaking |

## `uipath-langchain`

| Release | Date | What's relevant | Notes |
|---------|------|-----------------|-------|
| [v0.10.0](https://github.com/UiPath/uipath-langchain-python/releases/tag/v0.10.0) | 2026-04-23 | Transport/auth split into new `uipath-llm-client` and `uipath-langchain-client` packages (legacy preserved) | Non-breaking |

## `uipath-runtime`

| Release | Date | What's relevant | Notes |
|---------|------|-----------------|-------|
| [v0.3.0](https://github.com/UiPath/uipath-runtime-python/releases/tag/v0.3.0) | 2025-12-18 | `UiPathDebugBridgeProtocol` renamed to `UiPathDebugProtocol` | 🚨 Breaking (protocol implementers only) |
