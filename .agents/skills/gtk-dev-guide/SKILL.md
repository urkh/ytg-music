---
name: gtk-dev-guide
description: Guide for developing GTK4 and Libadwaita components, managing templates, and debugging UI.
---

# GTK4 & Libadwaita Development Guide

This skill provides architectural guidance, best practices, and debugging techniques for building UI components in `ytg-music` using GTK4 and Libadwaita.

---

## 1. Widget & Template Architecture

All major views (`views/*.py`) use GtkBuilder XML definitions located in `ui/*.ui`.

### Template Binding Pattern
```python
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

@Gtk.Template(filename='ui/my_view.ui')
class MyView(Adw.Bin):
    __gtype_name__ = 'MyView'

    # 1. Bind UI widgets declared in XML by their 'id'
    my_button = Gtk.Template.Child()
    my_list_box = Gtk.Template.Child()

    def __init__(self, parent_window, **kwargs):
        super().__init__(**kwargs)
        self.parent_window = parent_window

    # 2. Bind signal callbacks declared in XML
    @Gtk.Template.Callback()
    def on_my_button_clicked(self, button):
        self.do_something()
```

### Matching XML Structure (`ui/my_view.ui`)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <template class="MyView" parent="AdwBin">
    <property name="child">
      <object class="GtkBox">
        <property name="orientation">vertical</property>
        <child>
          <object class="GtkButton" id="my_button">
            <property name="label">Click Me</property>
            <signal name="clicked" handler="on_my_button_clicked" swapped="no"/>
          </object>
        </child>
        <child>
          <object class="GtkListBox" id="my_list_box">
            <style>
              <class name="boxed-list"/>
            </style>
          </object>
        </child>
      </object>
    </property>
  </template>
</interface>
```

---

## 2. Asynchronous Operations & Main Thread Marshaling

> [!WARNING]
> Never update GTK properties or add/remove widgets from worker threads. Always marshal back to the GLib main loop.

### Loading Data Asynchronously
```python
from services.worker import run_in_background
from services.ytmusic import api

def load_data(self):
    def fetch():
        # Background worker thread
        return api.get_artist(self.artist_id)

    def on_complete(result):
        # Dispatched to GTK main thread automatically
        if result:
            self.render_artist_details(result)

    def on_error(err):
        # Dispatched to GTK main thread automatically
        self.show_error_state(err)

    run_in_background(fetch, on_complete, on_error)
```

---

## 3. Reusable UI Components (`utils/ui_components.py`)

- **`create_item_card(app, item)`**: Generates visual media cards (artist circle, album square, playlist) with lazy thumbnail loading and fixed sizing.
- **`create_song_row(item)`**: Generates standard `Adw.ActionRow` for tracks.
- **`update_song_row(row, item)`**: Updates existing row content without re-allocating widgets to prevent UI churn and memory leaks.
- **`update_active_list_row(list_box, current_video_id)`**: Toggles CSS class `.active-queue-row` on currently playing song.
- **`show_error_page(view, content_widget)` / `hide_error_page(view, content_widget)`**: Overlays an `Adw.StatusPage` with a network error icon without disrupting container hierarchies.

---

## 4. UI Debugging with GTK Inspector

GTK4 includes an interactive inspector for inspecting the widget tree, CSS classes, live CSS styling, and signal emission.

```bash
# Launch application with the GTK Inspector enabled
GTK_DEBUG=interactive uv run python app.py
```

### Tips for CSS Tweaks (`ui/style.css`)
- Use standard Adw CSS classes: `.heading`, `.title-1`, `.title-2`, `.caption`, `.dim-label`, `.accent`, `.boxed-list`, `.card`, `.flat`, `.pill`, `.circular`.
- Custom CSS in `ui/style.css` is loaded during `do_activate()` in `app.py` at `Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION`.
