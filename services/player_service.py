import random
from typing import Any, Dict, List, Optional

import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, GObject, Gst  # noqa: E402
from pytubefix import YouTube  # noqa: E402

from services.worker import run_in_background  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.network import with_retries  # noqa: E402

logger = get_logger(__name__)

Gst.init(None)


class PlayerService(GObject.Object):
    __gsignals__ = {
        'state-changed': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),  # is_playing
        'loading-changed': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),  # is_loading
        'song-changed': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str, str, str),
        ),  # title, artist, thumb_url
        'error': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'position-changed': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (int, int),
        ),  # pos, dur
        'queue-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'queue-index-changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'volume-changed': (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        'seeked': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self):
        super().__init__()
        self.queue = []
        self.current_index = -1
        self.is_shuffle = False
        self.is_repeat = False

        self.player = Gst.ElementFactory.make('playbin', 'player')
        self.player.set_property('volume', 1.0)
        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self.on_message)
        self.is_playing = False
        self.is_loading = False
        self.current_video_id = None
        self.current_position = 0
        self.current_duration = 0
        self.current_title = ''
        self.current_artist = ''
        self.current_thumb_url = ''
        self.timer_id = 0

    def start_timer(self) -> None:
        if self.timer_id == 0:
            self.timer_id = GLib.timeout_add(1000, self.on_timer)

    def on_timer(self) -> bool:
        if not self.is_playing:
            return True

        success_pos, position = self.player.query_position(Gst.Format.TIME)
        success_dur, duration = self.player.query_duration(Gst.Format.TIME)

        # There are streams where query_duration temporarily fails, emit what we have
        pos_sec = position // Gst.SECOND if success_pos else 0
        dur_sec = duration // Gst.SECOND if success_dur else 0

        if success_pos:
            self.current_position = pos_sec
        if success_dur and dur_sec > 0:
            self.current_duration = dur_sec

        # Always emit if the position is valid
        if success_pos:
            self.emit('position-changed', pos_sec, self.current_duration)

        return True

    def play_queue(self, tracks: List[Dict[str, Any]], start_index: int = 0) -> None:
        self.queue = tracks
        self.emit('queue-changed')
        self.play_index(start_index)

    def append_to_queue(self, new_tracks: List[Dict[str, Any]]) -> None:
        self.queue.extend(new_tracks)
        self.emit('queue-changed')

    def play_index(self, index: int) -> None:
        if not self.queue or index < 0 or index >= len(self.queue):
            return

        self.current_index = index
        self.emit('queue-index-changed', self.current_index)

        track = self.queue[index]
        video_id = track.get('videoId')
        title = track.get('title', 'Unknown')

        artists = track.get('artists', [])
        artist_name = artists[0].get('name', 'Artist') if (artists and isinstance(artists, list)) else 'Artist'

        thumbnails = track.get('thumbnails', [])
        thumb_url = thumbnails[-1].get('url') if thumbnails else None

        self.play_video(video_id, title, artist_name, thumb_url)

    def next_song(self):
        if not self.queue:
            return

        if self.is_shuffle:
            if len(self.queue) > 1:
                next_idx = self.current_index
                while next_idx == self.current_index:
                    next_idx = random.randint(0, len(self.queue) - 1)
                self.play_index(next_idx)
            return

        if self.current_index >= 0 and self.current_index < len(self.queue) - 1:
            self.play_index(self.current_index + 1)
        elif self.is_repeat and len(self.queue) > 0:
            self.play_index(0)

    def prev_song(self):
        if not self.queue:
            return

        if self.current_index > 0:
            self.play_index(self.current_index - 1)
        elif self.is_repeat and len(self.queue) > 0:
            self.play_index(len(self.queue) - 1)

    def set_volume(self, value):
        # value expected between 0.0 and 1.0
        val = max(0.0, min(1.0, float(value)))
        self.player.set_property('volume', val)
        self.emit('volume-changed', val)

    def toggle_shuffle(self):
        self.is_shuffle = not self.is_shuffle
        return self.is_shuffle

    def toggle_repeat(self):
        self.is_repeat = not self.is_repeat
        return self.is_repeat

    def play_video(self, video_id, title, artist, thumb_url):
        if not video_id:
            return
        self.current_video_id = video_id
        self.current_title = title
        self.current_artist = artist
        self.current_thumb_url = thumb_url or ''
        self.current_position = 0
        self.current_duration = 0
        self.emit('song-changed', title, artist, thumb_url or '')

        # Stop current playback
        self.player.set_state(Gst.State.NULL)
        self.is_playing = False
        self.emit('state-changed', False)
        
        self.is_loading = True
        self.emit('loading-changed', True)

        # Resolve URL in background with retries
        @with_retries
        def fetch_url() -> Optional[str]:
            yt = YouTube(f'https://www.youtube.com/watch?v={video_id}', client='WEB_MUSIC')
            stream = yt.streams.get_audio_only()
            return stream.url if stream else None

        def on_url_resolved(url: Optional[str]) -> None:
            self.is_loading = False
            self.emit('loading-changed', False)
            if not url or self.current_video_id != video_id:
                return  # Failed or user changed song

            self.player.set_property('uri', url)
            self.player.set_state(Gst.State.PLAYING)
            self.is_playing = True
            self.emit('state-changed', True)
            self.start_timer()

        def on_url_error(e: Exception) -> None:
            self.is_loading = False
            self.emit('loading-changed', False)
            logger.error(f'Error extrayendo URL para video {video_id} tras reintentos: {e}')

        run_in_background(fetch_url, on_url_resolved, on_url_error)

    def toggle_play(self):
        if not self.current_video_id:
            return

        if self.is_playing:
            self.player.set_state(Gst.State.PAUSED)
            self.is_playing = False
        else:
            self.player.set_state(Gst.State.PLAYING)
            self.is_playing = True

        self.emit('state-changed', self.is_playing)

    def seek(self, position_sec):
        if not self.current_video_id:
            return

        position_sec = max(0, float(position_sec))
        # Simple seek requires time in nanoseconds and correct flags
        self.player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            int(position_sec * Gst.SECOND),
        )
        self.current_position = int(position_sec)
        self.emit('seeked', int(position_sec))
        self.emit('position-changed', int(position_sec), int(self.current_duration))

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.READY)
            self.is_playing = False
            self.emit('state-changed', False)
            self.next_song()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f'GStreamer error: {err}')
            self.player.set_state(Gst.State.NULL)
            self.is_playing = False
            self.emit('state-changed', False)
            self.emit('error', str(err))


player_service = PlayerService()
