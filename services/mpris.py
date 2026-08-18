import re
from typing import Any, Dict, Optional

from gi.repository import Gio, GLib, Gst

from services.player_service import player_service
from utils.logger import get_logger

logger = get_logger(__name__)

MPRIS_INTROSPECTION_XML = """<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/>
    <method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="Fullscreen" type="b" access="readwrite"/>
    <property name="CanSetFullscreen" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Pause"/>
    <method name="PlayPause"/>
    <method name="Stop"/>
    <method name="Play"/>
    <method name="Seek">
      <arg direction="in" name="Offset" type="x"/>
    </method>
    <method name="SetPosition">
      <arg direction="in" name="TrackId" type="o"/>
      <arg direction="in" name="Position" type="x"/>
    </method>
    <method name="OpenUri">
      <arg direction="in" name="Uri" type="s"/>
    </method>
    <signal name="Seeked">
      <arg name="Position" type="x"/>
    </signal>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="LoopStatus" type="s" access="readwrite"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Shuffle" type="b" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>
"""


class MPRISService:
    """
    Implements the MPRIS 2 D-Bus specification for native integration with GNOME Shell
    """
    OBJECT_PATH = '/org/mpris/MediaPlayer2'
    BUS_NAME = 'org.mpris.MediaPlayer2.ytgmusic'

    def __init__(self, app: Any):
        self.app = app
        self.connection: Optional[Gio.DBusConnection] = None
        self._registered_ids: list[int] = []
        self._owner_id: int = 0

        self._node_info = Gio.DBusNodeInfo.new_for_xml(MPRIS_INTROSPECTION_XML)
        self._root_iface = self._node_info.lookup_interface('org.mpris.MediaPlayer2')
        self._player_iface = self._node_info.lookup_interface('org.mpris.MediaPlayer2.Player')

        # Connect to signals
        player_service.connect('state-changed', self._on_player_state_changed)
        player_service.connect('song-changed', self._on_player_song_changed)
        player_service.connect('position-changed', self._on_player_position_changed)
        player_service.connect('queue-changed', self._on_player_queue_changed)
        player_service.connect('queue-index-changed', self._on_player_queue_changed)
        player_service.connect('volume-changed', self._on_player_volume_changed)
        player_service.connect('seeked', self._on_player_seeked)

        self._acquire_bus()

    def _acquire_bus(self) -> None:
        self._owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            self.BUS_NAME,
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            self._on_name_acquired,
            self._on_name_lost,
        )

    def _on_bus_acquired(self, connection: Gio.DBusConnection, name: str) -> None:
        self.connection = connection
        try:
            reg_root = connection.register_object(
                self.OBJECT_PATH,
                self._root_iface,
                self._handle_root_method_call,
                self._handle_root_get_prop,
                self._handle_root_set_prop,
            )
            reg_player = connection.register_object(
                self.OBJECT_PATH,
                self._player_iface,
                self._handle_player_method_call,
                self._handle_player_get_prop,
                self._handle_player_set_prop,
            )
            self._registered_ids.extend([reg_root, reg_player])
            logger.info(f'MPRIS service registered on {name} ({self.OBJECT_PATH})')
        except Exception as e:
            logger.error(f'Failed to register MPRIS D-Bus objects: {e}')

    def _on_name_acquired(self, connection: Gio.DBusConnection, name: str) -> None:
        logger.info(f'D-Bus name acquired: {name}')

    def _on_name_lost(self, connection: Optional[Gio.DBusConnection], name: str) -> None:
        logger.warning(f'D-Bus name lost: {name}')

    # Properties and Signals Notification
    def _emit_properties_changed(self, interface: str, changed_props: Dict[str, GLib.Variant]) -> None:
        if not self.connection:
            return
        variant = GLib.Variant(
            '(sa{sv}as)',
            (
                interface,
                changed_props,
                [],
            ),
        )
        try:
            self.connection.emit_signal(
                None,
                self.OBJECT_PATH,
                'org.freedesktop.DBus.Properties',
                'PropertiesChanged',
                variant,
            )
        except Exception as e:
            logger.debug(f'Error emitting MPRIS PropertiesChanged: {e}')

    def _on_player_state_changed(self, service: Any, is_playing: bool) -> None:
        self._emit_properties_changed(
            'org.mpris.MediaPlayer2.Player',
            {
                'PlaybackStatus': GLib.Variant('s', self._get_playback_status()),
                'CanPlay': GLib.Variant('b', self._can_play()),
                'CanPause': GLib.Variant('b', bool(player_service.current_video_id)),
            },
        )

    def _on_player_song_changed(self, service: Any, title: str, artist: str, thumb_url: str) -> None:
        self._emit_properties_changed(
            'org.mpris.MediaPlayer2.Player',
            {
                'Metadata': self._get_metadata_variant(),
                'CanSeek': GLib.Variant('b', bool(player_service.current_video_id)),
                'CanGoNext': GLib.Variant('b', self._can_go_next()),
                'CanGoPrevious': GLib.Variant('b', self._can_go_previous()),
            },
        )

    def _on_player_position_changed(self, service: Any, pos: int, dur: int) -> None:
        if dur > 0 and getattr(self, '_last_emitted_duration', 0) != dur:
            self._last_emitted_duration = dur
            self._emit_properties_changed(
                'org.mpris.MediaPlayer2.Player',
                {'Metadata': self._get_metadata_variant()},
            )

    def _on_player_queue_changed(self, service: Any, *args: Any) -> None:
        self._emit_properties_changed(
            'org.mpris.MediaPlayer2.Player',
            {
                'CanGoNext': GLib.Variant('b', self._can_go_next()),
                'CanGoPrevious': GLib.Variant('b', self._can_go_previous()),
            },
        )

    def _on_player_volume_changed(self, service: Any, volume: float) -> None:
        self._emit_properties_changed(
            'org.mpris.MediaPlayer2.Player',
            {'Volume': GLib.Variant('d', volume)},
        )

    def _on_player_seeked(self, service: Any, position_sec: int) -> None:
        if not self.connection:
            return
        pos_us = int(position_sec * 1_000_000)
        try:
            self.connection.emit_signal(
                None,
                self.OBJECT_PATH,
                'org.mpris.MediaPlayer2.Player',
                'Seeked',
                GLib.Variant('(x)', (pos_us,)),
            )
        except Exception as e:
            logger.debug(f'Error emitting MPRIS Seeked signal: {e}')

    def _get_playback_status(self) -> str:
        if player_service.is_playing:
            return 'Playing'
        elif player_service.current_video_id:
            return 'Paused'
        return 'Stopped'

    def _can_go_next(self) -> bool:
        q_len = len(player_service.queue)
        if q_len == 0:
            return False
        if player_service.is_repeat:
            return True
        if player_service.is_shuffle and q_len > 1:
            return True
        return 0 <= player_service.current_index < q_len - 1

    def _can_go_previous(self) -> bool:
        q_len = len(player_service.queue)
        if q_len == 0:
            return False
        if player_service.is_repeat:
            return True
        return player_service.current_index > 0

    def _can_play(self) -> bool:
        return bool(player_service.current_video_id or player_service.queue)

    def _get_metadata_variant(self) -> GLib.Variant:
        meta: Dict[str, GLib.Variant] = {}

        track: Dict[str, Any] = {}
        idx = player_service.current_index
        if 0 <= idx < len(player_service.queue):
            track = player_service.queue[idx]

        vid = player_service.current_video_id or track.get('videoId')
        if vid:
            clean_id = re.sub(r'[^a-zA-Z0-9_]', '_', str(vid))
            meta['mpris:trackid'] = GLib.Variant('o', f'/com/github/urkh/ytgmusic/track/{clean_id}')
            meta['xesam:url'] = GLib.Variant('s', f'https://music.youtube.com/watch?v={vid}')
        else:
            meta['mpris:trackid'] = GLib.Variant('o', '/org/mpris/MediaPlayer2/TrackList/NoTrack')

        title = track.get('title') or getattr(player_service, 'current_title', 'Unknown')
        meta['xesam:title'] = GLib.Variant('s', str(title))

        artists = track.get('artists', [])
        artist_name = artists[0].get('name') if (artists and isinstance(artists, list)) else 'Artist'
        if not artist_name:
            artist_name = getattr(player_service, 'current_artist', 'Artist')
        meta['xesam:artist'] = GLib.Variant('as', [str(artist_name)])

        album = track.get('album')
        if isinstance(album, dict) and album.get('name'):
            meta['xesam:album'] = GLib.Variant('s', str(album['name']))

        thumbnails = track.get('thumbnails', [])
        thumb_url = thumbnails[-1].get('url') if thumbnails else getattr(player_service, 'current_thumb_url', None)
        if thumb_url:
            meta['mpris:artUrl'] = GLib.Variant('s', str(thumb_url))

        dur = getattr(player_service, 'current_duration', 0)
        if dur > 0:
            meta['mpris:length'] = GLib.Variant('x', int(dur * 1_000_000))

        return GLib.Variant('a{sv}', meta)

    # --- Root Interface Handlers ---

    def _handle_root_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        if method_name == 'Raise':
            if hasattr(self.app, 'win') and self.app.win:
                GLib.idle_add(self.app.win.present)
            invocation.return_value(None)
        elif method_name == 'Quit':
            GLib.idle_add(self.app.quit)
            invocation.return_value(None)
        else:
            invocation.return_error_literal(
                Gio.dbus_error_quark(),
                Gio.DBusError.UNKNOWN_METHOD,
                f'Unknown method: {method_name}',
            )

    def _handle_root_get_prop(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
    ) -> Optional[GLib.Variant]:
        if property_name == 'CanQuit':
            return GLib.Variant('b', True)
        elif property_name == 'Fullscreen':
            return GLib.Variant('b', False)
        elif property_name == 'CanSetFullscreen':
            return GLib.Variant('b', False)
        elif property_name == 'CanRaise':
            return GLib.Variant('b', True)
        elif property_name == 'HasTrackList':
            return GLib.Variant('b', False)
        elif property_name == 'Identity':
            return GLib.Variant('s', 'YTG Music')
        elif property_name == 'DesktopEntry':
            return GLib.Variant('s', 'com.github.urkh.ytgmusic')
        elif property_name == 'SupportedUriSchemes':
            return GLib.Variant('as', ['http', 'https'])
        elif property_name == 'SupportedMimeTypes':
            return GLib.Variant('as', ['audio/mpeg', 'audio/mp4', 'audio/webm', 'audio/ogg'])
        return None

    def _handle_root_set_prop(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
    ) -> bool:
        return True

    # Interface Handlers
    def _handle_player_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        if method_name == 'Next':
            GLib.idle_add(player_service.next_song)
            invocation.return_value(None)
        elif method_name == 'Previous':
            GLib.idle_add(player_service.prev_song)
            invocation.return_value(None)
        elif method_name == 'Pause':
            if player_service.is_playing:
                GLib.idle_add(player_service.toggle_play)
            invocation.return_value(None)
        elif method_name == 'PlayPause':
            GLib.idle_add(player_service.toggle_play)
            invocation.return_value(None)
        elif method_name == 'Stop':
            def do_stop():
                player_service.player.set_state(Gst.State.NULL)
                player_service.is_playing = False
                player_service.emit('state-changed', False)
            GLib.idle_add(do_stop)
            invocation.return_value(None)
        elif method_name == 'Play':
            if not player_service.is_playing:
                GLib.idle_add(player_service.toggle_play)
            invocation.return_value(None)
        elif method_name == 'Seek':
            offset_us = parameters.unpack()[0]
            offset_sec = offset_us / 1_000_000.0
            pos = getattr(player_service, 'current_position', 0)
            target = max(0, pos + offset_sec)
            GLib.idle_add(player_service.seek, target)
            invocation.return_value(None)
        elif method_name == 'SetPosition':
            track_id, pos_us = parameters.unpack()
            pos_sec = pos_us / 1_000_000.0
            GLib.idle_add(player_service.seek, pos_sec)
            invocation.return_value(None)
        elif method_name == 'OpenUri':
            invocation.return_value(None)
        else:
            invocation.return_error_literal(
                Gio.dbus_error_quark(),
                Gio.DBusError.UNKNOWN_METHOD,
                f'Unknown method: {method_name}',
            )

    def _handle_player_get_prop(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
    ) -> Optional[GLib.Variant]:
        if property_name == 'PlaybackStatus':
            return GLib.Variant('s', self._get_playback_status())
        elif property_name == 'LoopStatus':
            return GLib.Variant('s', 'Playlist' if player_service.is_repeat else 'None')
        elif property_name == 'Rate':
            return GLib.Variant('d', 1.0)
        elif property_name == 'Shuffle':
            return GLib.Variant('b', bool(player_service.is_shuffle))
        elif property_name == 'Metadata':
            return self._get_metadata_variant()
        elif property_name == 'Volume':
            vol = player_service.player.get_property('volume')
            return GLib.Variant('d', float(vol))
        elif property_name == 'Position':
            success_pos, position = player_service.player.query_position(Gst.Format.TIME)
            if success_pos:
                return GLib.Variant('x', int(position // 1000))
            return GLib.Variant('x', int(getattr(player_service, 'current_position', 0) * 1_000_000))
        elif property_name == 'MinimumRate':
            return GLib.Variant('d', 1.0)
        elif property_name == 'MaximumRate':
            return GLib.Variant('d', 1.0)
        elif property_name == 'CanGoNext':
            return GLib.Variant('b', self._can_go_next())
        elif property_name == 'CanGoPrevious':
            return GLib.Variant('b', self._can_go_previous())
        elif property_name == 'CanPlay':
            return GLib.Variant('b', self._can_play())
        elif property_name == 'CanPause':
            return GLib.Variant('b', bool(player_service.current_video_id))
        elif property_name == 'CanSeek':
            return GLib.Variant('b', bool(player_service.current_video_id))
        elif property_name == 'CanControl':
            return GLib.Variant('b', True)
        return None

    def _handle_player_set_prop(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
    ) -> bool:
        if property_name == 'LoopStatus':
            val_str = value.unpack()
            player_service.is_repeat = val_str in ('Playlist', 'Track')
            self._emit_properties_changed(
                'org.mpris.MediaPlayer2.Player',
                {'LoopStatus': GLib.Variant('s', 'Playlist' if player_service.is_repeat else 'None')},
            )
            return True
        elif property_name == 'Shuffle':
            player_service.is_shuffle = bool(value.unpack())
            self._emit_properties_changed(
                'org.mpris.MediaPlayer2.Player',
                {'Shuffle': GLib.Variant('b', player_service.is_shuffle)},
            )
            return True
        elif property_name == 'Volume':
            vol = max(0.0, min(1.0, float(value.unpack())))
            GLib.idle_add(player_service.set_volume, vol)
            return True
        return False
