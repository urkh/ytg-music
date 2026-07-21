import html
import re


def format_description(text: str) -> str:
    """
    Takes the description from ytmusicapi and converts it to HTML/Pango markup,
    making links clickable and preserving line breaks.
    """
    if not text:
        return ''

    text = html.escape(text)

    def replace_url(match):
        url = match.group(0)
        href = url if url.startswith('http') else 'http://' + url
        return f'<a href="{href}">{url}</a>'

    url_pattern = re.compile(r'(https?://[^\s]+|www\.[^\s]+)')
    text = url_pattern.sub(replace_url, text)

    text = re.sub(r'\n+', '\n\n', text)

    return text
