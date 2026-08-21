import json

from gi.repository import Adw, Gdk, GLib, Gtk

from services.image_loader import load_image_async
from services.worker import run_in_background
from services.ytmusic import reload_api
from utils.auth import (
    build_base_headers,
    extract_browser_cookies,
    find_valid_accounts,
    get_auth_file_path,
    poll_oauth_token,
    save_oauth_token,
    start_oauth_flow,
)
from utils.i18n import _


@Gtk.Template(filename='ui/login_dialog.ui')
class LoginDialog(Adw.Window):
    __gtype_name__ = 'LoginDialog'

    lbl_instructions = Gtk.Template.Child()
    btn_extract_cookies = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    content_box = Gtk.Template.Child()
    stack = Gtk.Template.Child()
    lbl_oauth_url = Gtk.Template.Child()
    lbl_oauth_code = Gtk.Template.Child()
    btn_oauth = Gtk.Template.Child()
    btn_oauth_cancel = Gtk.Template.Child()
    btn_open_browser = Gtk.Template.Child()
    oauth_spinner = Gtk.Template.Child()

    def __init__(self, parent_window, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        self.set_transient_for(parent_window)
        self._is_closed = False
        self._poll_id = None
        self._device_code = None
        self._verification_url = None

        self.spinner.set_spinning(False)
        self.spinner.set_visible(False)
        self.oauth_spinner.set_spinning(False)
        self.oauth_spinner.set_visible(False)
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
    def on_oauth_clicked(self, btn):
        self.btn_oauth.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.set_spinning(True)
        self.lbl_instructions.set_label('Starting OAuth Device Flow...')

        def start_flow():
            try:
                return start_oauth_flow()
            except Exception as e:
                return e

        def on_started(result):
            if self._is_closed:
                return
            self.spinner.set_spinning(False)
            self.spinner.set_visible(False)

            if isinstance(result, Exception):
                self.lbl_instructions.set_label(_('Error: ') + str(result))
                self.btn_oauth.set_sensitive(True)
                return

            self._device_code = result['device_code']
            self._verification_url = result['verification_url']

            self.lbl_oauth_url.set_label(self._verification_url)
            self.lbl_oauth_code.set_label(result['user_code'])
            self.stack.set_visible_child_name('page_oauth')

            interval = result.get('interval', 5)
            self._poll_id = GLib.timeout_add_seconds(interval, self.poll_token)

        run_in_background(start_flow, on_started)

    def poll_token(self):
        if self._is_closed or self.stack.get_visible_child_name() != 'page_oauth':
            self._poll_id = None
            return False

        def do_poll():
            try:
                return poll_oauth_token(self._device_code)
            except Exception as e:
                return e

        def on_poll(result):
            if self._is_closed or self.stack.get_visible_child_name() != 'page_oauth':
                return

            if isinstance(result, Exception):
                return  # Network error or something else, keep polling

            if isinstance(result, dict):
                if 'error' in result:
                    if result['error'] == 'authorization_pending':
                        return  # Keep polling
                    else:
                        self.lbl_oauth_code.set_label(_('Error: ') + result['error'])
                        return

                if 'access_token' in result:
                    if self._poll_id:
                        GLib.source_remove(self._poll_id)
                        self._poll_id = None

                    self.oauth_spinner.set_spinning(True)
                    self.oauth_spinner.set_visible(True)
                    self.lbl_oauth_code.set_label(_('Success! Logging in...'))

                    def save_task():
                        save_oauth_token(result)
                        return True

                    def on_saved(res):
                        reload_api()
                        GLib.timeout_add(500, self.finish_login)

                    run_in_background(save_task, on_saved)

        run_in_background(do_poll, on_poll)
        return True

    @Gtk.Template.Callback()
    def on_open_browser_clicked(self, btn):
        if self._verification_url:
            Gtk.show_uri(self, self._verification_url, Gdk.CURRENT_TIME)

    @Gtk.Template.Callback()
    def on_oauth_cancel_clicked(self, btn):
        self.stack.set_visible_child_name('page_main')
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = None
        self.btn_oauth.set_sensitive(True)
        self.lbl_instructions.set_label(
            'To log in, make sure you are logged into YouTube Music in your primary browser.'
        )

    @Gtk.Template.Callback()
    def on_close_request(self, dialog):
        self._is_closed = True
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = None
        return False
