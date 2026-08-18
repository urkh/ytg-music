import sys

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gst', '1.0')

from gi.repository import Adw, Gdk, Gio, GObject, Gtk  # noqa: E402

from services.mpris import MPRISService  # noqa: E402
from utils.i18n import setup_i18n  # noqa: E402
from utils.logger import setup_logging  # noqa: E402
from views.window import MainWindow  # noqa: E402


class YTGMusic(Adw.Application):
    __gsignals__ = {
        'login-state-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__(
            application_id='com.github.urkh.ytgmusic',
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.mpris_service = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.mpris_service = MPRISService(self)

    def do_activate(self):
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        provider = Gtk.CssProvider()
        provider.load_from_path('ui/style.css')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        if not self.props.active_window:
            self.win = MainWindow(app=self, application=self)

        self.win.present()

    def navigate_to(self, view_name, **kwargs):
        if hasattr(self, 'win'):
            self.win.navigate_to(view_name, **kwargs)


def main():
    setup_logging()
    setup_i18n()
    app = YTGMusic()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
