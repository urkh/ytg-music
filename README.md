# YouTube Music Desktop Client

A modern, native GTK4 client for YouTube Music built with Python.

## Features

- **Modern UI**: Adwaita-styled, responsive design.
- **Playback Control**: Play, pause, skip, shuffle, repeat.
- **Queue Management**: View, reorder, and manage the current queue.
- **Navigation**: Easy switching between Home, Explore, and Library.
- **Search**: Instant search suggestions and dedicated results page.
- **Authentication**: Secure login flow.
- **Memory Management**: Automatic cleanup of unused views to free RAM.
- **Internationalization**: Multi-language support (English, Spanish, Russian, etc.).

## Getting Started

### Prerequisites

- Python 3.9+
- GTK4
- MessageBus (dbus)
- Meson (build system)

### Installation

1.  **Clone the repository**
2.  **Install Dependencies**:

    Using uv:
    ```bash
    uv pip install -r requirements.txt
    ```

### Running the Application

```bash
uv run python app.py
```