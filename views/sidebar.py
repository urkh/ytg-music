from gi.repository import Gtk, Pango

from services.image_loader import load_image_async
from services.worker import run_in_background
from services.ytmusic import api
from utils.auth import is_authenticated
from utils.i18n import _
from views.login import LoginDialog


@Gtk.Template(filename='ui/sidebar.ui')
class SidebarView(Gtk.Box):
    __gtype_name__ = 'SidebarView'

    nav_list = Gtk.Template.Child()
    btn_login = Gtk.Template.Child()
    row_library = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        if self.row_library:
            self.row_library.set_visible(False)

        self.check_login_state()

        app_instance = self.app.app if hasattr(self.app, 'app') else self.app
        if hasattr(app_instance, 'connect'):
            app_instance.connect('login-state-changed', lambda *args: self.check_login_state())

    def check_login_state(self):
        if is_authenticated():
            self.btn_login.set_sensitive(False)
            if self.row_library:
                self.row_library.set_visible(True)

            def fetch_user_info():
                try:
                    return api.get_account_info()
                except Exception:
                    return None

            def on_info_loaded(info):
                if not info:
                    self.btn_login.set_label(_('Connected'))
                    return

                name = info.get('accountName', _('Connected'))
                photo_url = info.get('accountPhotoUrl')

                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                box.set_halign(Gtk.Align.CENTER)

                img = Gtk.Image.new_from_icon_name('avatar-default-symbolic')
                img.set_pixel_size(24)
                if photo_url:
                    load_image_async(photo_url, img, is_circular=True)

                lbl = Gtk.Label(label=name)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                lbl.set_max_width_chars(15)

                box.append(img)
                box.append(lbl)

                self.btn_login.set_child(box)

            run_in_background(fetch_user_info, on_info_loaded)

    @Gtk.Template.Callback()
    def on_login_clicked(self, button):
        LoginDialog(self.app, self.app)
