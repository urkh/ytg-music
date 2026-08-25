---
name: flatpak-build
description: Build, install, run, and debug the Flatpak package locally using flatpak-builder.
---

# Flatpak Build & Packaging Workflow

This skill explains how to build, test, and debug the `ytg-music` Flatpak bundle locally using `flatpak-builder` and the GNOME 49 Platform.

---

## 1. Prerequisites

Ensure `flatpak` and `flatpak-builder` are installed on the host system:

```bash
# Debian / Ubuntu / Pop!_OS
sudo apt install flatpak flatpak-builder

# Fedora
sudo dnf install flatpak flatpak-builder

# Arch Linux
sudo pacman -S flatpak flatpak-builder
```

Install the required GNOME 49 runtime and SDK:

```bash
flatpak install --user flathub org.gnome.Platform//49 org.gnome.Sdk//49
```

---

## 2. Building and Installing Locally

Build and install the application locally into the user's Flatpak repository:

```bash
# Clean build and install
flatpak-builder --user --install --force-clean build-dir com.github.urkh.ytgmusic.yml
```

### Running the Installed Flatpak
```bash
flatpak run com.github.urkh.ytgmusic
```

### Creating a Standalone Bundle File (`.flatpak`)
To package a single-file bundle distribution:
```bash
flatpak-builder --force-clean --repo=repo build-dir com.github.urkh.ytgmusic.yml
flatpak build-bundle repo com.github.urkh.ytgmusic.flatpak com.github.urkh.ytgmusic
```

---

## 3. Flatpak Manifest Overview (`com.github.urkh.ytgmusic.yml`)

Key sandbox permissions (`finish-args`):
- `--share=ipc`, `--socket=wayland`, `--socket=fallback-x11`: Windowing system and graphics display.
- `--share=network`: Accessing YouTube API and media streaming.
- `--socket=pulseaudio`: Audio playback through PipeWire / PulseAudio.
- `--own-name=org.mpris.MediaPlayer2.ytgmusic`: D-Bus permission to expose MPRIS controls on the session bus.
- `--talk-name=org.freedesktop.secrets`: Secret service access for credentials.
- `--filesystem=home:ro`: Read-only access to host home (used for browser cookies during login).

---

## 4. Debugging in Flatpak Sandbox

### Opening a Shell Inside the Sandbox
To inspect installed files, dependencies, or environment variables inside the sandboxed container:

```bash
flatpak run --command=sh com.github.urkh.ytgmusic
```

### Inspecting Installed Application Files
Inside the container:
```sh
ls -la /app/share/ytgmusic/
python3 -c "import gi, ytmusicapi, pytubefix; print('Imports successful')"
```
