# YTG Music — Agent Development Guide

`ytg-music` is a native, modern desktop client for YouTube Music built with Python 3.11+, GTK4, Libadwaita, and GStreamer. This document defines the architectural conventions, concurrency guidelines, coding style, testing protocols, and release workflows for AI agents and human contributors working on this repository.

---

## 1. Tech Stack & Dependencies

- **Language & Runtime**: Python >= 3.11 managed via [`uv`](https://github.com/astral-sh/uv).
- **GUI Framework**: GTK4 (`gi.repository.Gtk`) + Libadwaita (`gi.repository.Adw`) via PyGObject (`gi.repository`).
- **Audio Engine**: GStreamer 1.0 (`gi.repository.Gst`) using `playbin` pipeline.
- **YouTube Services**:
  - `ytmusicapi`: YouTube Music internal API client (navigation, search, explore, library, artist/album metadata).
  - `pytubefix`: Audio stream resolution from YouTube videos.
  - `browsercookie`: Browser cookie extraction for Google/YouTube Music authentication.
- **Data Modeling**: `pydantic` v2 (`BaseModel`, `ConfigDict(extra='allow')`).
- **Desktop Integration**: MPRIS D-Bus interface (`org.mpris.MediaPlayer2.ytgmusic` via `services/mpris.py`).
- **Packaging & Sandboxing**: Flatpak with GNOME 49 runtime (`com.github.urkh.ytgmusic.yml`).
- **Tooling**: `ruff` for linting/formatting, `pytest` + `pytest-recording` (VCR.py) for testing.

---

## 2. Repository Architecture & Layout

```
ytg-music/
├── app.py                     # Main application entry point (Adw.Application) & CSS loading
├── pyproject.toml             # Project metadata, dependencies, ruff & pytest configurations
├── uv.lock                    # Dependency lockfile
├── com.github.urkh.ytgmusic.yml # Flatpak manifest
├── models/
│   └── media.py               # Pydantic models (MediaItem, AlbumDetail, ArtistDetail, etc.)
├── services/
│   ├── image_loader.py        # Async image downloader, Cairo/GdkPixbuf processing, disk cache
│   ├── mpris.py               # D-Bus MPRIS v2 implementation (media keys, lock screen integration)
│   ├── player_service.py      # GStreamer playbin manager, queue, volume, position signals
│   ├── worker.py              # ThreadPoolExecutor for background tasks with GLib.idle_add callback
│   └── ytmusic.py             # YTMusic API singleton proxy with retries & auth token handling
├── views/
│   ├── window.py              # MainWindow controller (stack navigation, search suggestions)
│   ├── player.py              # Bottom playback bar and full player controls
│   ├── queue.py               # Playback queue drawer, lyrics, related items
│   ├── home.py                # Home feed view
│   ├── explore.py             # Explore & trending view
│   ├── library.py             # User library view (playlists, songs, albums, artists)
│   ├── artist.py              # Artist details & top tracks view
│   ├── album.py               # Album tracks & details view
│   ├── sidebar.py             # Navigation sidebar
│   └── login.py               # OAuth / Cookie login dialogs
├── ui/
│   ├── *.ui                   # GtkBuilder XML definitions for views and dialogs
│   └── style.css              # Custom CSS rules augmenting Libadwaita styles
├── utils/
│   ├── auth.py                # Cookie and OAuth authentication utilities
│   ├── formatters.py          # Time and text formatting utilities
│   ├── i18n.py                # Gettext localization setup
│   ├── logger.py              # Standardized logging configuration
│   ├── network.py             # Network retry decorator (@with_retries)
│   └── ui_components.py       # Reusable UI widgets (cards, song rows, error pages)
├── locales/                   # Translation catalogs (.pot / .po)
└── tests/
    ├── conftest.py            # Global fixtures (sync worker mocking, anonymous mode override)
    ├── test_services.py       # Unit tests for services, models, image processing, MPRIS
    ├── test_auth.py           # Unit tests for authentication utilities
    └── cassettes/             # Recorded VCR HTTP interactions for API tests
```

---

## 3. Core Development Rules & Patterns

### 3.1. GTK Thread Safety & Concurrency (CRITICAL)

> [!CAUTION]
> GTK4 and Libadwaita are strictly **NOT** thread-safe. Modifying GTK widgets or calling UI methods directly from a background thread will cause memory corruption, race conditions, or hard crashes (`SIGSEGV`).

- **Never** manipulate GTK widgets directly from background worker threads.
- Always use `services.worker.run_in_background(task_func, on_complete, on_error)` for executing network calls, heavy I/O, or audio stream extractions:
  ```python
  from services.worker import run_in_background

  def fetch_data():
      # Runs in background ThreadPoolExecutor
      return api.get_artist(artist_id)

  def on_loaded(data):
      # Automatically dispatched to GTK main loop via GLib.idle_add
      if data:
          self.populate_ui(data)

  def on_error(err):
      logger.error(f'Failed to load artist: {err}')
      self.show_error()

  run_in_background(fetch_data, on_loaded, on_error)
  ```
- If scheduling a manual callback from an asynchronous operation, wrap it in `GLib.idle_add(callback, *args)`.

### 3.2. Image Loading & Memory Management

- Use `services.image_loader.load_image_async(url, widget, is_circular=False, is_unrounded=False, max_size=200)` for loading images.
- Images are cached on disk under `~/.cache/ytg-music/thumbnails/`.
- Do not keep unneeded textures or high-resolution pixbufs permanently in RAM. When updating list rows, clear the old image widget (`img.clear()`) before loading new content.
- Use `process_pixbuf()` which preserves aspect ratios during downscaling and applies smooth clipping via Cairo.

### 3.3. Data Models & API Handling

- All YouTube Music data should be parsed into typed Pydantic models from `models/media.py` (e.g., `MediaItem`, `AlbumDetail`, `ArtistDetail`).
- Use `parse_media_item(raw_dict)` to convert unstructured `ytmusicapi` responses into reliable `MediaItem` instances.
- Always configure Pydantic models with `model_config = ConfigDict(extra='allow')` to remain resilient against unexpected upstream API response changes.

### 3.4. UI Templates & Libadwaita Conventions

- Views inherit from Adw/Gtk classes and bind to `.ui` template files via the `@Gtk.Template(filename='ui/<name>.ui')` decorator.
- Use `Gtk.Template.Child()` to reference UI components declared in XML.
- Use `Gtk.Template.Callback()` for signal handlers declared in `.ui` files.
- Follow GNOME Human Interface Guidelines (HIG): Use standard Adw widgets (`Adw.ApplicationWindow`, `Adw.HeaderBar`, `Adw.ViewStack`, `Adw.ActionRow`, `Adw.StatusPage`, `Adw.ToastOverlay`, `Adw.Breakpoint`).

### 3.5. Audio Playback & Extraction

- Playback is orchestrated through the singleton `services.player_service.player_service`.
- GStreamer `playbin` is used for audio output. Listen to player signals (`song-changed`, `state-changed`, `position-changed`, `queue-changed`, etc.) rather than querying state manually.
- Stream resolution uses `pytubefix` with automatic retries via `@with_retries`. Extraction failures must be caught gracefully without crashing the queue.

### 3.6. Simplicity & Minimal Surface Area

- Fixes should make the system simpler, not more complex. Prefer removing or consolidating code over adding a new layer, flag, or special case. If a fix grows the system's surface area, look for the version that shrinks it.

---

## 4. Coding Style & Zero-Comments Standard

- **Linter & Formatter**: `ruff`
- **Line Length**: 120 characters
- **Quotes**: Single quotes (`'`) for Python string literals
- **Imports**: Grouped and sorted via `isort` with known first parties:
  ```toml
  known-first-party = ["models", "services", "utils", "views", "ui"]
  ```
- **Zero-Comments Standard**: Never leave comments in the repo. The standard is zero comments: no explanatory comments or docblocks, TODO/FIXME notes, lint/type suppression directives, or commented-out code. Express intent through names, structure, and tests; put rationale in commit messages or PR descriptions. Interpreter shebangs are executable directives, not comments.

---

## 5. Standard Development Commands

### Running Locally
```bash
# Run application with uv
uv run python app.py

# Run with interactive GTK Inspector (for CSS & widget debugging)
GTK_DEBUG=interactive uv run python app.py
```

### Linting & Formatting
```bash
# Check code for linting errors
uv run ruff check .

# Automatically fix lint issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Running Tests
```bash
# Run all unit tests
uv run pytest

# Run tests in a headless environment (using xvfb)
xvfb-run -a uv run pytest

# Run a specific test file
uv run pytest tests/test_services.py

# Update / record VCR cassettes when API endpoints change
uv run pytest --record-mode=rewrite tests/test_services.py
```

### Flatpak Build & Run
```bash
# Build and install locally
flatpak-builder --user --install --force-clean build-dir com.github.urkh.ytgmusic.yml

# Run installed Flatpak
flatpak run com.github.urkh.ytgmusic
```

---

## 6. Testing Conventions & VCR.py

- Tests in `tests/` use `pytest`, `pytest-mock`, and `pytest-recording`.
- `tests/conftest.py` automatically:
  1. Mocks `run_in_background` to run synchronously, eliminating race conditions in test runs.
  2. Forces anonymous mode (preventing tests from accessing local user credentials).
- Network-bound tests use `@pytest.mark.vcr()` to record HTTP interactions to YAML files in `tests/cassettes/`.
- Sensitive headers (`Authorization`, `Cookie`, `x-origin`) are filtered automatically by `vcr_config` in `conftest.py`.

---

## 7. Versioning & Release Workflow

1. Bump `version` in `pyproject.toml` (e.g. `0.0.4` -> `0.0.5`).
2. Commit changes:
   ```bash
   git commit -am "chore: bump version to 0.0.5"
   git push origin main
   ```
3. Tag and push release tag:
   ```bash
   git tag v0.0.5
   git push origin v0.0.5
   ```
4. GitHub Actions CI (`.github/workflows/flatpak.yml`) will automatically run tests, build the Flatpak bundle, and create a GitHub Release with the standalone `.flatpak` asset attached.
