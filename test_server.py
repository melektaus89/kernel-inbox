import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server

class ArchiveTests(unittest.TestCase):
    def test_list_ids_and_escaped_headers(self):
        for source in ('oss-security','linux-cve-announce'):
            parser=server.OpenwallParser(server.SOURCES[source]['index'],source)
            parser.feed('<ul><li>2026/09/10 #1: <a href="2026/09/10/1">CVE: &lt;script&gt;</a> (Alice &lt;a&#64;...org&gt;)<li>2026/09/10 #2: <a href="2026/09/10/2">Second</a> (Bob)</ul>')
            rows=parser.result()['messages']
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0],{'id':f'/{source}/2026/09/10/1','subject':'CVE: <script>','author':'Alice <a@...org>'})
            self.assertTrue(server.valid_id(rows[0]['id'],source))
            self.assertFalse(server.valid_id(rows[0]['id'],'lkml'))
        self.assertFalse(server.valid_id('/oss-security/../../etc/passwd','oss-security'))

    def test_body_and_folded_subject(self):
        parser=server.OpenwallParser('/oss-security/2026/09/10/1','oss-security')
        parser.feed('<a href="2">[next&gt;]</a><pre>\nFrom: Alice &lt;a&#64;...org&gt;\nDate: Today\nSubject: CVE disclosure\n continued\n\nA &lt;b&gt; body\n<a href="https://example.com">Link text</a>\n</pre>footer')
        message=parser.result()
        self.assertEqual(message['subject'],'CVE disclosure continued')
        self.assertEqual(message['body'],'A <b> body\nLink text\n')
        self.assertEqual(message['thread'],[]) # Adjacent mail is not a conversation.

    def test_separate_cache_and_stale_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'CACHE',Path(directory)), patch.object(server.urllib.request,'urlopen',side_effect=OSError('offline')):
            for source in ('oss-security','linux-cve-announce','lkml'):
                path=server.SOURCES[source]['index']
                cache=Path(directory)/(path.strip('/').replace('/','_')+'.json')
                cache.write_text(json.dumps({'messages':[{'id':source}],'fetched':0,'stale':False}))
                data=server.fetch_archive(path,300,source)
                self.assertTrue(data['stale'])
                self.assertEqual(data['messages'][0]['id'],source)

    def test_reject_invalid_archive_page(self):
        parser=server.OpenwallParser('/oss-security/','oss-security')
        parser.feed('<html>Service unavailable</html>')
        with self.assertRaises(ValueError): parser.result()


class LinusTests(unittest.TestCase):
    def test_sender_identity(self):
        self.assertTrue(server.is_linus('Linus Torvalds <>'))
        self.assertTrue(server.is_linus('Linus <torvalds@linux-foundation.org>'))
        self.assertFalse(server.is_linus('Linus Walleij'))
        self.assertFalse(server.is_linus('Linus Torvalds <someone@example.org>'))
        self.assertFalse(server.is_linus('Someone discussing Linus Torvalds'))

    def test_conversation_excludes_adjacent_messages(self):
        parser=server.ArchiveParser()
        parser.feed('<a href="/lkml/2026/9/9/1">Previous message</a><ul class="threadlist"><li><a href="/lkml/2026/9/9/2">First message in thread</a><ul><li><a href="/lkml/2026/9/9/3">Alice</a></li></ul></li></ul><a href="/lkml/2026/9/9/4">Next message</a>')
        self.assertEqual([m['id'] for m in parser.thread_links],['/lkml/2026/9/9/2','/lkml/2026/9/9/3'])

    def test_groups_threads_and_stale_fallback(self):
        rows=[{'id':f'/lkml/2026/9/9/{n}','subject':'Changed subject '+str(n),'author':'Linus Torvalds'} for n in (1,2)]
        def fetch(path,ttl):
            if server.ID.fullmatch(path):
                return {**next(r for r in rows if r['id']==path),'thread_root':rows[0]['id'],'stale':False}
            return {'messages':rows+[{'id':'/lkml/2026/9/9/3','author':'Linus Walleij','subject':'Other'}],'stale':False}
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'CACHE',Path(directory)), patch.object(server,'fetch_archive',side_effect=fetch):
            data=server.linus_feed()
            self.assertEqual([m['id'] for m in data['messages']],[rows[1]['id']])
            self.assertFalse(data['stale'])
            key=Path(directory)/'linus-feed.json'
            saved=json.loads(key.read_text());saved['fetched']=0;key.write_text(json.dumps(saved))
            with patch.object(server,'fetch_archive',side_effect=OSError('offline')):
                fallback=server.linus_feed()
            self.assertTrue(fallback['stale'])
            self.assertEqual(fallback['messages'],data['messages'])

class FeedTests(unittest.TestCase):
    def test_release_filter(self):
        for subject in ('Linux 7.3-rc2','Linux 7.2.4','[GIT PULL] fixes','[PULL v2] updates','[git pull] drm'):
            self.assertTrue(server.is_release_or_pull(subject),subject)
        for subject in ('Re: Linux 7.3-rc2','Re: [GIT PULL] fixes','[PATCH] Fix release handling','Linux performance issue'):
            self.assertFalse(server.is_release_or_pull(subject),subject)

    def test_release_feed_preserves_cache_when_new_day_unavailable(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'CACHE',Path(directory)), patch.object(server,'build_releases_feed',side_effect=OSError('offline')):
            (Path(directory)/'releases-feed.json').write_text(json.dumps({'messages':[{'id':'/lkml/2026/9/9/1'}],'fetched':0,'stale':False}))
            data=server.releases_feed()
            self.assertTrue(data['stale'])
            self.assertEqual(len(data['messages']),1)

    def test_atom_identity_body_and_parent(self):
        raw='''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:thr="http://purl.org/syndication/thread/1.0"><entry><author><name>Alice</name><email>a@example.org</email></author><title type="html">Re: &amp;lt;fix&amp;gt;</title><updated>2026-09-11T00:00:00Z</updated><link href="https://lore.kernel.ime.usp.br:443/regressions/test@example.org/"/><thr:in-reply-to href="https://lore.kernel.ime.usp.br/regressions/parent@example.org/"/><content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><pre>Hello &lt;world&gt;
<span>&gt; quoted</span></pre></div></content></entry></feed>'''
        row=server.atom_messages(raw,'regressions')[0]
        self.assertEqual(row['id'],'/regressions/test@example.org/')
        self.assertEqual(row['subject'],'Re: <fix>')
        self.assertEqual(row['body'],'Hello <world>\n> quoted')
        self.assertEqual(row['thread'][0]['id'],'/regressions/parent@example.org/')
        self.assertFalse(server.valid_id(row['id'],'stable'))
        self.assertFalse(server.valid_id('/regressions/..%2ftest@example.org/','regressions'))
        with self.assertRaises(ValueError): server.atom_messages(raw.replace('lore.kernel.ime.usp.br','evil.example'),'regressions')
        with self.assertRaises(ValueError): server.atom_messages('<html>Unavailable</html>','regressions')

    def test_atom_cache_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'CACHE',Path(directory)), patch.object(server.urllib.request,'urlopen',side_effect=OSError('offline')):
            for source in ('regressions','stable','linux-next'):
                path=server.SOURCES[source]['index']
                server.cache_key(path,source).write_text(json.dumps({'messages':[{'id':source}],'fetched':0,'stale':False}))
                data=server.fetch_archive(path,300,source)
                self.assertTrue(data['stale'])
                self.assertEqual(data['messages'][0]['id'],source)

class PortabilityTests(unittest.TestCase):
    def test_theme_without_omarchy(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server.Path, 'home', return_value=Path(directory)):
            self.assertEqual(server.theme(), {'name': 'Ethereal', 'colors': {}})

    def test_theme_can_be_disabled(self):
        with patch.dict(server.os.environ, {'KERNEL_INBOX_THEME': 'default'}), patch.object(server.Path, 'home', side_effect=AssertionError('must not read theme')):
            self.assertEqual(server.theme()['colors'], {})

    def test_custom_port_serves_api_and_rejects_foreign_host(self):
        import http.client
        import threading
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
            connection.request('GET', '/api/theme')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn('colors', json.loads(response.read()))
            connection.request('GET', '/api/theme', headers={'Host': 'foreign.example'})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            worker.join()

if __name__=='__main__': unittest.main()
