"""Public RSS/Atom retrieval with bounded responses and public-address-only connections."""
import hashlib
import http.client
import ipaddress
import socket
import ssl
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

MAX_BYTES = 5_000_000


def validate_url(value):
    if len(value) > 4096 or any(ord(c) < 33 for c in value):
        raise ValueError('Invalid feed URL.')
    url = urllib.parse.urlsplit(value)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise ValueError('Use a public http:// or https:// RSS or Atom URL.')
    if url.port not in (None, 80, 443):
        raise ValueError('Feed URLs must use standard HTTP or HTTPS ports.')
    return url


def fetch_public(url, redirects=0):
    parsed = validate_url(url)
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Feed URLs must point to a public internet address.')
    # Connect to a validated address directly, so DNS cannot change between checks and use.
    address = addresses[0]
    sock = socket.socket(address[0], address[1], address[2])
    sock.settimeout(20)
    connection = http.client.HTTPConnection(parsed.hostname, port, timeout=20)
    try:
        sock.connect(address[4])
        if parsed.scheme == 'https':
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
        connection.sock = sock
        target = urllib.parse.urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
        connection.request('GET', target, headers={'User-Agent':'KernelInbox/1.0', 'Accept':'application/atom+xml, application/rss+xml, application/xml, text/xml', 'Accept-Encoding':'identity'})
        response = connection.getresponse()
        if response.status in (301, 302, 303, 307, 308):
            if redirects >= 4:
                raise ValueError('Too many feed redirects.')
            location = response.getheader('Location')
            if not location:
                raise ValueError('Feed redirect has no destination.')
            destination = urllib.parse.urljoin(url, location)
            connection.close()
            return fetch_public(destination, redirects + 1)
        if response.status != 200:
            raise ValueError('The feed server did not return a feed.')
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Feed exceeds the 5 MB size limit.')
        return raw, url
    finally:
        connection.close()
        sock.close()


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('br', 'p', 'div', 'li', 'pre') and not self.hidden: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'li', 'pre') and not self.hidden: self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def plain(value):
    parser = TextOnly(); parser.feed(value); return ''.join(parser.parts).strip()


def parse_feed(raw, feed_url, resolved_url=None):
    # Reject DTDs/entities before parsing (including UTF-16 encoded declarations).
    if b'<!DOCTYPE' in raw.replace(b'\x00', b'').upper() or b'<!ENTITY' in raw.replace(b'\x00', b'').upper():
        raise ValueError('Feeds containing document type or entity declarations are unsupported.')
    root = ET.fromstring(raw)
    atom = '{http://www.w3.org/2005/Atom}'
    if root.tag == atom+'feed': entries = root.findall(atom+'entry'); is_atom = True
    elif root.tag == 'rss' and root.find('channel') is not None: entries = root.findall('channel/item'); is_atom = False
    else: raise ValueError('This URL is not an RSS 2.0 or Atom feed.')
    rows = []; seen = set()
    for entry in entries[:100]:
        def text(path):
            node = entry.find(path)
            return ''.join(node.itertext()).strip() if node is not None else ''
        if is_atom:
            title_node = entry.find(atom+'title')
            subject = text(atom+'title')
            if title_node is not None and title_node.get('type') == 'html': subject = plain(subject)
            author = text(atom+'author/'+atom+'name')
            date = text(atom+'published') or text(atom+'updated')
            link = next((n.get('href', '') for n in entry.findall(atom+'link') if n.get('rel', 'alternate') == 'alternate'), '')
            identity = text(atom+'id') or link
            content = entry.find(atom+'content')
            if content is None: content = entry.find(atom+'summary')
            body = '' if content is None else ''.join(content.itertext())
            if content is not None and content.get('type') == 'html': body = plain(body)
        else:
            subject = plain(text('title')); author = text('author') or text('{http://purl.org/dc/elements/1.1/}creator')
            date = text('pubDate') or text('{http://purl.org/dc/elements/1.1/}date')
            link = text('link'); identity = text('guid') or link
            body = plain(text('{http://purl.org/rss/1.0/modules/content/}encoded') or text('description'))
            try:
                parsed = parsedate_to_datetime(date)
                date = parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).isoformat()
            except (TypeError, ValueError, IndexError): pass
        absolute = urllib.parse.urljoin(resolved_url or feed_url, link)
        try:
            parsed_link = urllib.parse.urlsplit(absolute)
            if parsed_link.scheme not in ('http','https') or not parsed_link.hostname or parsed_link.username or parsed_link.password: absolute = feed_url
        except ValueError: absolute = feed_url
        mid = 'feed:'+hashlib.sha256((feed_url+'\n'+(identity or subject+'\n'+date+'\n'+body)).encode()).hexdigest()
        if mid in seen: continue
        seen.add(mid)
        rows.append({'id':mid, 'subject':subject or '(Untitled)', 'author':author or 'Unknown author', 'date':date, 'body':body, 'url':absolute, 'thread':[]})
    return rows
