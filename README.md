# YouTube Music Desktop Client

[![Release](https://img.shields.io/github/v/release/urkh/ytg-music?logo=github&style=flat-square)](https://github.com/urkh/ytg-music/releases)
[![Build](https://github.com/urkh/ytg-music/actions/workflows/flatpak.yml/badge.svg)](https://github.com/urkh/ytg-music/actions/workflows/flatpak.yml)
[![GTK4 / Libadwaita](https://img.shields.io/badge/GTK4-Libadwaita-4a90d9?logo=gnome&logoColor=white&style=flat-square)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white&style=flat-square)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg?style=flat-square)](https://www.gnu.org/licenses/gpl-3.0)

A modern, native GTK4 / Libadwaita client for YouTube Music built with Python.

## Features

- **Modern UI**: Adwaita-styled, native GNOME design adhering to GNOME HIG.
- **Playback Control**: Play, pause, skip, seek, volume, shuffle, and repeat.
- **MPRIS Integration**: Full integration with GNOME Shell sound menu, lock screen, and hardware media keys.
- **Queue Management**: View and manage the current playback queue, view lyrics and similar artists.
- **Navigation**: Home, Explore, and Library views with instant navigation.
- **Search**: Real-time search suggestions and dedicated results page.

## Installation & Getting Started

### Option 1: Install with Flatpak (Recommended)

Download the latest `com.github.urkh.ytgmusic.flatpak` bundle from the [Releases](https://github.com/urkh/ytg-music/releases) page, then install and run:

```bash
flatpak install --user com.github.urkh.ytgmusic.flatpak
flatpak run com.github.urkh.ytgmusic
```

### Option 2: Run from Source

#### Prerequisites
- Python 3.11+
- GTK4 / Libadwaita
- GStreamer 1.0
- D-Bus (for MPRIS integration)

#### Running with `uv`:
```bash
uv run python app.py
```

## Planned Features & Roadmap

### 1. Desktop & Adaptive Integration
- **Adaptive Breakpoints (`Adw.Breakpoint`)**: Dynamic UI adjustments for small screens or tiling (<800px), collapsing the sidebar into a drawer and hiding/collapsing the queue panel.
- **Keyboard Shortcuts & Help Window**: Standard GNOME shortcuts (`Space` for play/pause, `Ctrl+F` or `/` for search, `Ctrl+Q` to quit, `Alt+Left` to go back) and an `Adw.ShortcutsWindow` (`Ctrl+?`).
- **Packaging & Metadata**:
  - [x] Desktop entry file (`com.github.urkh.ytgmusic.desktop`) with quicklist playback actions.
  - [x] AppStream metadata (`com.github.urkh.ytgmusic.metainfo.xml`) for GNOME Software and Flatpak packaging.
  - [x] Automated Flatpak CI/CD packaging via GitHub Actions.

### 2. Audio Engine & Extraction Resilience
- **Multi-backend Extraction (`yt-dlp` fallback)**: Add `yt-dlp` support alongside `pytubefix` for resilient audio stream extraction against YouTube cipher changes.
- **Stream Link Cache**: In-session caching of stream URLs to minimize redundant extraction requests.

### 3. Cache & Storage Management
- **Thumbnail Disk Cache Pruning**: Automatic maintenance routine to cap `~/.cache/ytg-music/thumbnails/` under a configured limit (e.g., 200 MB) with LRU/mtime pruning.

### 4. YouTube Music UX & Features
- **Radio Mode / Infinite Autoplay**: Automatic recommendation queues (`radio=True`) when reaching the end of playlists or starting track radio.
- **Track & Album Context Menus**: Secondary actions menu (right click / `...` button) for "Play next", "Add to queue", "Start radio", "Go to album/artist", and "Add to playlist".
- **Search & Library Filters**: Filter chips for All, Songs, Albums, Artists, Playlists, and Videos, along with infinite scroll / pagination on demand.
- **OAuth Device Flow Authentication**: Clean browser-independent login via `google.com/device` for sandboxed Flatpak/Snap environments *(Blocked upstream by YouTube changes, see [ytmusicapi #813](https://github.com/sigma67/ytmusicapi/issues/813))*.
- **In-App Toast Notifications (`Adw.ToastOverlay`)**: Non-intrusive feedback toasts for actions like "Added to queue", "Subscribed", or network errors.
- **Complete Internationalization (i18n)**: Comprehensive localization support and complete translation coverage across all UI views and dialogs.