import re
import html as html_lib
import bleach

TAGS = ['p', 'br', 'div', 'span', 'b', 'strong', 'i', 'em', 'u', 's', 'code', 'pre', 'ul', 'ol', 'li', 'blockquote', 'a', 'img', 'h1', 'h2', 'h3']
IMAGE_ID = re.compile(r'[0-9a-f-]{36}')


def _attr(tag, name, value):
    if tag == 'a': return name in ('href', 'title', 'target', 'rel')
    if tag == 'img':
        if name == 'data-image-id': return bool(IMAGE_ID.fullmatch(value))
        if name == 'data-width': return bool(re.fullmatch(r'[0-9]{2,3}', value)) and 10 <= int(value) <= 100
        return name == 'data-align' and value in ('left', 'center', 'right')
    return False


def clean_description(raw):
    """Sanitized HTML, its plain-text version and the image ids it references."""
    # Drop <script>/<style> tags along with their inner content before bleach (bleach strips the tag but keeps content).
    pre = re.sub(r'<(script|style)\b[^>]*>.*?</\1\s*>', '', raw or '', flags=re.IGNORECASE | re.DOTALL)
    pre = re.sub(r'<(script|style)\b[^>]*/?>', '', pre, flags=re.IGNORECASE)
    clean = bleach.clean(pre, tags=TAGS, attributes=_attr, protocols=['http', 'https', 'mailto'], strip=True)
    clean = re.sub(r'<img(?![^>]*data-image-id)[^>]*>', '', clean).strip()
    text = re.sub(r'<(br|/p|/div|/li|/h[1-3]|/blockquote)[^>]*>', '\n', clean)
    text = re.sub(r'\n{3,}', '\n\n', html_lib.unescape(re.sub(r'<[^>]+>', '', text))).strip()
    return clean, text, set(re.findall(r'data-image-id="([0-9a-f-]{36})"', clean))
