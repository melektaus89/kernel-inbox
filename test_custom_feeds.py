import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import custom_feeds
import server


class CustomFeedTests(unittest.TestCase):
    def test_rss_content_dates_and_safe_links(self):
        raw = b'''<rss version="2.0"><channel><item><guid>one</guid><title>Example</title><author>Alice</author><pubDate>Sat, 19 Sep 2026 10:00:00 GMT</pubDate><link>javascript:alert(1)</link><description>&lt;p&gt;Hello&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;</description></item></channel></rss>'''
        rows = custom_feeds.parse_feed(raw, 'https://example.org/feed')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['body'], 'Hello')
        self.assertEqual(rows[0]['url'], 'https://example.org/feed')
        self.assertEqual(rows[0]['date'], '2026-09-19T10:00:00+00:00')
        self.assertNotEqual(rows[0]['id'], custom_feeds.parse_feed(raw, 'https://other.example/feed')[0]['id'])

    def test_atom_relative_links_and_plain_text(self):
        raw = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>one</id><title>Patch</title><link rel="self" href="ignore"/><link href="/article"/><author><name>Bob</name></author><content type="text">Hello &lt;kernel&gt;\n+ patch line</content></entry></feed>'''
        row = custom_feeds.parse_feed(raw, 'https://example.org/feed')[0]
        self.assertEqual(row['body'], 'Hello <kernel>\n+ patch line')
        self.assertEqual(row['url'], 'https://example.org/article')
        self.assertEqual(row['author'], 'Bob')
        self.assertEqual(custom_feeds.parse_feed(b'<rss><channel/></rss>', 'https://example.org/feed'), [])

    def test_invalid_and_entity_feeds(self):
        for raw in (b'<html/>', b'<!DOCTYPE rss [<!ENTITY x "hello">]><rss><channel/></rss>', '<!DOCTYPE rss><rss><channel/></rss>'.encode('utf-16')):
            with self.assertRaises(ValueError): custom_feeds.parse_feed(raw, 'https://example.org/feed')

    def test_public_url_validation(self):
        for url in ('file:///etc/passwd', 'https://user:pass@example.org/feed', 'http://example.org:22/feed', 'https://example.org/\nfoo'):
            with self.assertRaises(ValueError): custom_feeds.validate_url(url)
        for ip in ('127.0.0.1', '192.168.1.1', '169.254.169.254', '::1'):
            with patch.object(custom_feeds.socket, 'getaddrinfo', return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,80))]), patch.object(custom_feeds.socket,'socket') as sock:
                with self.assertRaises(ValueError): custom_feeds.fetch_public('http://example.org/feed')
                sock.assert_not_called()

    def test_redirect_to_private_address_is_rejected(self):
        response = MagicMock(status=302)
        response.getheader.return_value = 'http://127.0.0.1/private'
        connection = MagicMock(); connection.getresponse.return_value = response
        with patch.object(custom_feeds.socket,'getaddrinfo',side_effect=[[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',80))],[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',80))]]), patch.object(custom_feeds.socket,'socket') as sock, patch.object(custom_feeds.http.client,'HTTPConnection',return_value=connection):
            with self.assertRaises(ValueError): custom_feeds.fetch_public('http://example.org/feed')
            sock.return_value.connect.assert_called_once_with(('93.184.216.34',80))

    def test_cache_and_stale_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'CACHE',Path(directory)), patch.object(server,'fetch_public',return_value=(b'<rss><channel><item><title>Saved</title></item></channel></rss>','https://example.org/feed')) as fetch:
            data=server.custom_feed('https://example.org/feed')
            self.assertFalse(data['stale'])
            self.assertEqual(server.custom_feed('https://example.org/feed'),data)
            self.assertEqual(fetch.call_count,1)
            key=next(Path(directory).glob('custom_*.json'))
            data['fetched']=0;key.write_text(json.dumps(data))
            fetch.side_effect=OSError('offline')
            self.assertTrue(server.custom_feed('https://example.org/feed')['stale'])

    def test_http_endpoint(self):
        import http.client
        import threading
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            connection=http.client.HTTPConnection('127.0.0.1',httpd.server_port)
            with patch.object(server,'fetch_public',return_value=(b'<rss><channel/></rss>','https://example.org/feed')), tempfile.TemporaryDirectory() as directory, patch.object(server,'CACHE',Path(directory)):
                connection.request('GET','/api/feed?url=https%3A%2F%2Fexample.org%2Ffeed')
                response=connection.getresponse(); self.assertEqual(response.status,200)
                self.assertEqual(json.loads(response.read())['messages'],[])
            connection.request('GET','/api/feed?url=file:///etc/passwd')
            response=connection.getresponse();self.assertEqual(response.status,400)
            self.assertIn('error',json.loads(response.read()))
            connection.close()
        finally:
            httpd.shutdown();httpd.server_close();thread.join()
