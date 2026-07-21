import json

from gi.repository import Adw, GLib, Gtk

from services.image_loader import load_image_async
from services.worker import run_in_background
from services.ytmusic import reload_api
from utils.auth import (
    build_base_headers,
    extract_browser_cookies,
    find_valid_accounts,
    get_auth_file_path,
)
from utils.i18n import _


@Gtk.Template(filename='ui/login_dialog.ui')
class LoginDialog(Adw.Window):
    __gtype_name__ = 'LoginDialog'

    lbl_instructions = Gtk.Template.Child()
    btn_extract_cookies = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    content_box = Gtk.Template.Child()

    def __init__(self, parent_window, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        self.set_transient_for(parent_window)
        self._is_closed = False
        self.spinner.set_spinning(False)
        self.spinner.set_visible(False)
        self.present()

    @Gtk.Template.Callback()
    def on_extract_clicked(self, btn):
        self.btn_extract_cookies.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.set_spinning(True)
        self.lbl_instructions.set_label('Extracting cookies from YouTube Music...')

        def extract_cookies():
            try:
                cookie_str = extract_browser_cookies()
                base_headers = build_base_headers(cookie_str)
                return find_valid_accounts(base_headers)
            except Exception as e:
                return e

        def on_extracted(result):
            if self._is_closed:
                return

            self.spinner.set_spinning(False)
            self.spinner.set_visible(False)

            if isinstance(result, Exception):
                self.lbl_instructions.set_label(_('Error: ') + str(result))
                self.btn_extract_cookies.set_sensitive(True)
                return

            self.lbl_instructions.set_label(_('Select the channel you want to use:'))
            self.btn_extract_cookies.set_visible(False)

            for account in result:
                btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                btn_box.set_halign(Gtk.Align.CENTER)

                img = Gtk.Image.new_from_icon_name('avatar-default-symbolic')
                img.set_pixel_size(32)
                if account.get('photo_url'):
                    load_image_async(account['photo_url'], img, is_circular=True)

                lbl = Gtk.Label(label=f'{account["name"]} ({account["handle"]})')
                lbl.set_valign(Gtk.Align.CENTER)

                btn_box.append(img)
                btn_box.append(lbl)

                btn = Gtk.Button()
                btn.set_child(btn_box)
                btn.add_css_class('pill')
                btn.connect('clicked', self.on_account_selected, account)
                self.content_box.append(btn)

        run_in_background(extract_cookies, on_extracted)

    def on_account_selected(self, btn, account_info):
        child = self.content_box.get_first_child()
        while child:
            if isinstance(child, Gtk.Button):
                child.set_sensitive(False)
            child = child.get_next_sibling()

        headers_path = get_auth_file_path()
        with open(headers_path, 'w') as f:
            json.dump(account_info['headers'], f, indent=2)

        self.lbl_instructions.set_label('Logged in')

        reload_api()
        GLib.timeout_add(1000, self.finish_login)

    def finish_login(self):
        if not self._is_closed:
            self.close()
            app_instance = self.app.app if hasattr(self.app, 'app') else self.app
            app_instance.emit('login-state-changed')
        return False

    @Gtk.Template.Callback()
    def on_close_request(self, dialog):
        self._is_closed = True
        return False
