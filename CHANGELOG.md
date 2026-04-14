# Changelog

All notable changes to this project are documented in this file.

## [Unreleased] - 2026-04-13

### Added
- Browser automation research tool (`browser_research`) with Playwright integration in backend toolchain.
- Screenshot capture support for browser research, including preview URL output.
- Telegram command `/status_tasks` to list task statuses across recent tasks.
- Chat inspector tabs for Info/Logs/Preview and tool-level preview exposure in UI.
- Backend preview endpoints and proxy routes for local generated content/app servers.
- Legacy preview-link normalization in Telegram responses.
- New contributor guides:
  - `CONTRIBUTING.md` (canonical)
  - `contibution.md` (compatibility alias for legacy references)
- New dependency split files:
  - `backend/requirements-core.txt`
  - `backend/requirements-optional.txt`

### Changed
- Stabilized backend dependency installation strategy:
  - `backend/requirements.txt` now points to stable core dependencies only.
  - Optional/private dependency `emergentintegrations==0.1.0` moved out of the mandatory install path.
- Updated autonomy planning allowlist to include browser-based research when needed.
- Updated server and Telegram guidance so tool prompts include browser-driven research flow.
- Updated deployment and maintenance documentation to use core+optional dependency installation flow.
- Updated tool execution behavior to better handle long-running local servers by relaunching in detached/background mode when appropriate.
- Updated preview URL generation strategy for reverse-proxied/Azure environments where backend ports are not publicly reachable.
- Updated autonomous learning cadence to be configurable via settings.

### Fixed
- Prevented full environment rebuild failures caused by unavailable `emergentintegrations` on public indexes.
- Improved autonomy notifications by allowing optional Telegram push for significant autonomous actions.
- Enabled optional Telegram morning learning digest notifications.
- Improved task advancement behavior by transitioning eligible tasks (`pending`/`planned`) to `in_progress` with next-step notes.
- Removed AI-model footer line from Telegram message output.
- Improved preview resolution for generated web projects so renderable entry files are preferred over directory listing views.
- Reduced stale/legacy preview links in Telegram by rewriting older URL formats.

### Security
- Enforced safer execution boundaries for generated work in temporary workspace patterns (sandbox-oriented workflow).
- Restricted agent tooling from modifying project source tree by default in autonomous/generated flows, preferring temporary sandbox workspace.
- Propagated Telegram credentials into generated subprocess environments for explicit notification use-cases.

### UX
- Improved task visibility in Telegram via status-focused command output.
- Improved web research capability for JS-rendered/interactive websites.
- Improved observability of agent actions through preview/log oriented chat interactions.

### Docs
- Updated `README.md` with dependency policy and optional install path.
- Updated `DEPLOYMENT.md` for install, update, and troubleshooting commands.
- Updated `DEPLOYMENT_STATUS.md` to reflect optional dependency strategy and corrected reinstall commands.
- Added complete historical summary in this changelog for recent autonomy, preview, Telegram, safety, and dependency workstreams.

### Notes
- Playwright runtime requires browser binaries and system dependencies in Linux environments.
- Recommended provisioning sequence for browser tool support:
  1. `pip install playwright==1.54.0`
  2. `playwright install chromium`
  3. `playwright install-deps chromium`
