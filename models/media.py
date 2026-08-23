from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HomeSection(BaseModel):
    model_config = ConfigDict(extra='allow')
    title: Optional[str] = None
    contents: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class TrendingSection(BaseModel):
    model_config = ConfigDict(extra='allow')
    items: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class MoodGenre(BaseModel):
    model_config = ConfigDict(extra='allow')
    title: str = ''
    params: str = ''


class ExploreData(BaseModel):
    model_config = ConfigDict(extra='allow')
    new_releases: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    trending: Optional[TrendingSection] = None
    moods_and_genres: Optional[List[MoodGenre]] = Field(default_factory=list)


class LibrarySection(BaseModel):
    model_config = ConfigDict(extra='allow')
    title: str = ''
    contents: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    force_type: str = ''


class MediaItem(BaseModel):
    """
    Model that validates raw ytmusicapi response dictionaries
    """

    model_config = ConfigDict(extra='allow')

    title: str = Field(default='Unknown')
    resultType: str = Field(default='song', alias='resultType')

    videoId: Optional[str] = None
    browseId: Optional[str] = None
    playlistId: Optional[str] = None

    thumbnails: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    artists: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    author: Optional[Any] = Field(default_factory=list)
    description: Optional[str] = None

    duration: Optional[str] = None
    album: Optional[Dict[str, Any]] = None
    year: Optional[str] = None

    @property
    def best_thumbnail_url(self) -> Optional[str]:
        if not self.thumbnails or not isinstance(self.thumbnails, list):
            return None
        return self.thumbnails[-1].get('url')

    @property
    def display_subtitle(self) -> str:
        """
        Calculates the subtitle to display on the card depending on the result type
        """
        if self.resultType == 'artist':
            return 'Artist'

        elif self.resultType == 'playlist':
            if self.author:
                if isinstance(self.author, list) and len(self.author) > 0 and isinstance(self.author[0], dict):
                    return self.author[0].get('name', 'Playlist')
                elif isinstance(self.author, str):
                    return self.author
            if self.description:
                return self.description
            return 'Playlist'

        else:
            artist_name = ''
            if self.artists and isinstance(self.artists, list) and len(self.artists) > 0:
                artist_name = self.artists[0].get('name', 'Artist')
            elif self.author:
                if isinstance(self.author, list) and len(self.author) > 0 and isinstance(self.author[0], dict):
                    artist_name = self.author[0].get('name', 'Artist')
                elif isinstance(self.author, str):
                    artist_name = self.author

            if self.resultType == 'album':
                if self.year:
                    return f'{self.year}'
                if artist_name:
                    return f'Album • {artist_name}'
                return 'Album'

            return artist_name

    @property
    def display_title(self) -> str:
        return self.title

    def to_queue_track(self, fallback_artist: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Serializes this item to a dictionary format compatible with the player
        """
        artists = self.artists or []
        if not artists and self.author:
            if isinstance(self.author, list):
                artists = self.author
            elif isinstance(self.author, str):
                artists = [{'name': self.author, 'id': None}]
        if not artists and fallback_artist:
            artists = [fallback_artist]

        return {
            'videoId': self.videoId,
            'title': self.title,
            'artists': artists,
            'thumbnails': self.thumbnails or [],
            'album': self.album or {},
            'duration': self.duration or '',
        }


def parse_media_item(data: dict, force_type: Optional[str] = None) -> MediaItem:
    """
    Convert a raw dictionary into a MediaItem
    """
    parsed_data = dict(data)

    if parsed_data.get('thumbnails') is None:
        parsed_data['thumbnails'] = []
    if parsed_data.get('artists') is None:
        parsed_data['artists'] = []
    if parsed_data.get('author') is None:
        parsed_data['author'] = []

    if force_type:
        parsed_data['resultType'] = force_type
    elif 'resultType' not in parsed_data:
        if 'videoId' in parsed_data:
            parsed_data['resultType'] = 'song'
        elif 'playlistId' in parsed_data:
            parsed_data['resultType'] = 'playlist'
        elif 'browseId' in parsed_data:
            b_id = parsed_data['browseId']
            if b_id.startswith('UC'):
                parsed_data['resultType'] = 'artist'
            elif b_id.startswith('MPREb_'):
                parsed_data['resultType'] = 'album'
            else:
                parsed_data['resultType'] = 'album'

    if parsed_data.get('resultType') == 'artist' and 'title' not in parsed_data:
        if 'artist' in parsed_data and isinstance(parsed_data['artist'], str):
            parsed_data['title'] = parsed_data['artist']
        elif 'artists' in parsed_data and isinstance(parsed_data['artists'], list) and len(parsed_data['artists']) > 0:
            parsed_data['title'] = parsed_data['artists'][0].get('name', 'Unknown')

    if 'title' not in parsed_data and parsed_data.get('name'):
        parsed_data['title'] = parsed_data['name']

    return MediaItem.model_validate(parsed_data)


class ArtistDetail(BaseModel):
    model_config = ConfigDict(extra='allow')

    name: str = Field(default='Unknown')
    subscribers: Optional[str] = None
    description: Optional[str] = None
    subscribed: bool = False
    thumbnails: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    songs: Optional[Dict[str, Any]] = Field(default_factory=dict)
    albums: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @property
    def display_subscribers(self) -> str:
        if self.subscribers:
            subs = self.subscribers.lower().replace('subscribers', '').replace('suscriptores', '').strip().upper()
            return f'Monthly listeners: {subs} users'
        return ''

    @property
    def best_thumbnail_url(self) -> Optional[str]:
        if not self.thumbnails or not isinstance(self.thumbnails, list):
            return None
        return self.thumbnails[-1].get('url')


class AlbumDetail(BaseModel):
    model_config = ConfigDict(extra='allow')

    title: str = Field(default='Unknown')
    artists: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    year: Optional[str] = None
    trackCount: int = 0
    description: Optional[str] = None
    thumbnails: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tracks: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    @property
    def artist_name(self) -> str:
        if self.artists and isinstance(self.artists, list) and len(self.artists) > 0:
            return self.artists[0].get('name', 'Artist')
        return 'Artist'

    @property
    def artist_id(self) -> Optional[str]:
        if self.artists and isinstance(self.artists, list) and len(self.artists) > 0:
            return self.artists[0].get('id')
        return None

    @property
    def best_thumbnail_url(self) -> Optional[str]:
        if not self.thumbnails or not isinstance(self.thumbnails, list):
            return None
        return self.thumbnails[-1].get('url')

    def get_queue_tracks(self, album_id: str) -> List[Dict[str, Any]]:
        queue = []
        tracks = self.tracks or []
        for track in tracks:
            video_id = track.get('videoId')
            if not video_id:
                continue

            queue.append(
                {
                    'videoId': video_id,
                    'title': track.get('title', 'Unknown'),
                    'artists': track.get('artists') or self.artists or [],
                    'thumbnails': self.thumbnails or [],
                    'album': {'name': self.title, 'id': album_id},
                    'year': self.year,
                }
            )
        return queue
