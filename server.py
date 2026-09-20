#!/usr/bin/env python3
"""Loopback-only LKML reader. No external Python dependencies."""
import argparse, os, json, re, time, tomllib, urllib.request, urllib.parse, threading, hashlib
import xml.etree.ElementTree as ET
from custom_feeds import validate_url, fetch_public, parse_feed
from html import unescape
from email.parser import Parser
from email.utils import parseaddr
from datetime import datetime, timedelta, timezone
from pathlib import Path
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
ROOT = Path(__file__).resolve().parent
CACHE = Path(os.environ.get('KERNEL_INBOX_CACHE_DIR', str(ROOT / '.cache'))).expanduser()
CACHE.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()
FEED_LOCK = threading.Lock()
LINUS_EMAIL = 'torvalds@linux-foundation.org'
ID = re.compile(r'/lkml/\d{4}/\d{1,2}/\d{1,2}/\d+')
SOURCES = {
    **{name: {'base':'https://lore.kernel.org', 'index':f'/{name}/new.atom', 'kind':'atom'} for name in ('regressions','stable','linux-next')},
    'netdev': {'base':'https://lists.openwall.net', 'index':'/netdev/'},
    'lkml': {'base':'https://lkml.org', 'index':'/lkml/last100'},
    'linux-cve-announce': {'base':'https://lists.openwall.net', 'index':'/linux-cve-announce/'},
    'oss-security': {'base':'https://www.openwall.com/lists', 'index':'/oss-security/'},
}
def valid_id(mid, source):
    if SOURCES.get(source,{}).get('kind')=='atom':
        match = re.fullmatch('/'+re.escape(source)+r'/([^/?#\s]+)/',mid)
        return bool(match and '@' in urllib.parse.unquote(match[1]) and not any(c in urllib.parse.unquote(match[1]) for c in '/\\\r\n'))
    return re.fullmatch(r'/' + re.escape(source) + r'/\d{4}/\d{1,2}/\d{1,2}/\d+', mid)

class OpenwallParser(HTMLParser):
    def __init__(self, path, source):
        super().__init__(); self.path=path; self.source=source; self.rows=[]; self.row=None; self.anchor=False; self.pre=False; self.body=''
    def finish_row(self):
        if self.row and self.row.get('id'):
            self.rows.append({'id':self.row['id'], 'subject':' '.join(self.row['subject'].split()), 'author':self.row['author'].strip().removeprefix('(').removesuffix(')')})
        self.row=None
    def handle_starttag(self, tag, attrs):
        if tag=='li': self.finish_row(); self.row={'subject':'','author':''}; self.anchor=False
        if tag=='pre': self.pre=True
        if tag=='a' and self.row is not None:
            href=dict(attrs).get('href','')
            mid=urllib.parse.urljoin(self.path, href)
            if valid_id(mid,self.source): self.row['id']=mid; self.anchor=True
        if tag=='br' and self.pre: self.body+='\n'
    def handle_endtag(self, tag):
        if tag=='a': self.anchor=False
        if tag in ('ul','li'): self.finish_row()
        if tag=='pre': self.pre=False
    def handle_data(self, data):
        if self.pre: self.body+=data
        if self.row is not None and self.row.get('id'):
            self.row['subject' if self.anchor else 'author']+=data
    def result(self):
        self.finish_row()
        if self.path==SOURCES[self.source]['index']:
            if not self.rows: raise ValueError('No messages found')
            return {'messages':self.rows[:100]}
        mail=Parser().parsestr(self.body.lstrip('\n'))
        if not mail.get('Subject') or not mail.get('From'): raise ValueError('Message body unavailable')
        return {'id':self.path,'subject':' '.join(mail['Subject'].split()),'author':mail['From'],'date':mail.get('Date',''),'body':mail.get_payload(),'thread':[]}

class ArchiveParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.link=None; self.links=[]; self.fields={}; self.field=None; self.thread_depth=0; self.thread_links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='ul' and (self.thread_depth or a.get('class')=='threadlist'): self.thread_depth+=1
        if tag=='tr' and a.get('class') in ('c0','c1'): self.row=[]
        if tag=='a' and ID.fullmatch(a.get('href','')): self.link={'id':a['href'],'text':''}
        if a.get('itemprop') in ('articleBody','author','datePublished','name'): self.field=a['itemprop']; self.fields[self.field]=''
        if tag=='br' and self.field: self.fields[self.field]+='\n'
    def handle_data(self, data):
        if self.link is not None: self.link['text']+=data
        if self.field: self.fields[self.field]+=data
    def handle_endtag(self, tag):
        if tag=='a' and self.link is not None:
            self.links.append(self.link)
            if self.thread_depth: self.thread_links.append(self.link)
            if self.row is not None: self.row.append(self.link)
            self.link=None
        if tag=='tr' and self.row is not None:
            if len(self.row)>=2: self.rows.append({'id':self.row[0]['id'],'subject':self.row[0]['text'].strip(),'author':self.row[1]['text'].strip()})
            self.row=None
        if tag=='ul' and self.thread_depth: self.thread_depth-=1
        if tag in ('pre','td'): self.field=None

def atom_messages(raw, source):
    root=ET.fromstring(raw)
    if root.tag!='{http://www.w3.org/2005/Atom}feed': raise ValueError('Invalid Atom feed')
    ns={'a':'http://www.w3.org/2005/Atom','t':'http://purl.org/syndication/thread/1.0'}
    def message_path(href):
        url=urllib.parse.urlsplit(href)
        if url.hostname not in ('lore.kernel.org','lore.kernel.ime.usp.br') or not valid_id(url.path,source):
            raise ValueError('Invalid archive message link')
        return url.path
    rows=[]
    for entry in root.findall('a:entry',ns):
        mid=message_path(entry.find('a:link',ns).get('href',''))
        name=entry.findtext('a:author/a:name','',ns)
        address=entry.findtext('a:author/a:email','',ns)
        content=entry.find('a:content',ns)
        body=''.join(content.itertext()) if content is not None else ''
        parent=entry.find('t:in-reply-to',ns)
        thread=[]
        if parent is not None and parent.get('href'):
            thread=[{'id':message_path(parent.get('href')), 'text':'Parent message'}]
        rows.append({'id':mid, 'subject':unescape(entry.findtext('a:title','',ns)),
                     'author':f'{name} <{address}>' if address else name,
                     'date':entry.findtext('a:updated','',ns), 'body':body, 'thread':thread})
    if not rows: raise ValueError('No messages found')
    return rows

CACHE_LOCKS={}
def cache_lock(key):
    with LOCK: return CACHE_LOCKS.setdefault(str(key),threading.Lock())

def cache_key(path, source):
    if SOURCES[source].get('kind')=='atom':
        return CACHE / (source+'_'+hashlib.sha256(path.encode()).hexdigest()+'.json')
    return CACHE / (path.strip('/').replace('/','_')+'.json')

def fetch_archive(path, ttl, source="lkml"):
    key=cache_key(path,source)
    with cache_lock(key):
        cached=json.loads(key.read_text()) if key.exists() else None
        if cached and time.time()-cached['fetched']<ttl: return cached
        try:
            atom=SOURCES[source].get('kind')=='atom'
            request_path=path+'t.atom' if atom and valid_id(path,source) else path
            req=urllib.request.Request(SOURCES[source]['base']+request_path,headers={'User-Agent':'KernelInbox/1.0 (local mailing-list reader)'})
            with urllib.request.urlopen(req,timeout=20) as r: raw=r.read(5_000_000).decode('utf-8','replace')
            parser=ArchiveParser() if source=='lkml' else OpenwallParser(path,source)
            if not atom: parser.feed(raw)
            if atom:
                rows=atom_messages(raw,source)
                if path==SOURCES[source]['index']:
                    data={'messages':[{k:m[k] for k in ('id','subject','author','date')} for m in rows[:100]], 'latest':rows[0]['date']}
                else:
                    data=next(m for m in rows if m['id']==path)
                    data['thread']=[{'id':m['id'],'text':m['subject']+' — '+m['author']} for m in rows if m['id']!=path]
            elif source!='lkml':
                data=parser.result()
            elif path=='/lkml/last100' or re.fullmatch(r'/lkml/\d{4}/\d{1,2}/\d{1,2}',path):
                if not parser.rows: raise ValueError('No messages found in archive response')
                data={'messages':parser.rows[:100] if path=='/lkml/last100' else parser.rows}
            else:
                if 'articleBody' not in parser.fields: raise ValueError('Message body unavailable')
                data={'id':path,'subject':parser.fields.get('name',''),'author':parser.fields.get('author',''),'date':parser.fields.get('datePublished',''),'body':parser.fields['articleBody'], 'thread':list({x['id']:x for x in parser.thread_links if x['id']!=path}.values()), 'thread_root':next((x['id'] for x in parser.thread_links if x['text']=='First message in thread'),path)}
            result={**data,'fetched':time.time(),'source':SOURCES[source]['base']+path,'stale':False}
            key.write_text(json.dumps(result)); return result
        except Exception:
            if cached: return {**cached,'stale':True}
            raise

def custom_feed(url):
    validate_url(url)
    key = CACHE / ('custom_' + hashlib.sha256(url.encode()).hexdigest() + '.json')
    with cache_lock(key):
        cached = json.loads(key.read_text()) if key.exists() else None
        if cached and time.time() - cached['fetched'] < 300: return cached
        try:
            raw, resolved = fetch_public(url)
            result = {'messages':parse_feed(raw, url, resolved), 'fetched':time.time(), 'stale':False}
            key.write_text(json.dumps(result))
            return result
        except Exception:
            if cached: return {**cached, 'stale':True}
            raise


def is_linus(author):
    name, address = parseaddr(author)
    if address and '@' in address:
        return address.casefold() == LINUS_EMAIL
    # LKML.org redacts From addresses. Only use the exact full sender name;
    # mentions, quoted text, signatures, and other people named Linus do not count.
    return sender_name(author).casefold() == 'linus torvalds'

def linus_feed():
    key = CACHE / 'linus-feed.json'
    with FEED_LOCK:
        cached = json.loads(key.read_text()) if key.exists() else None
        if cached and time.time() - cached['fetched'] < 300:
            return cached
        try:
            today = datetime.now(timezone.utc).date()
            candidates = {}; stale = False
            for offset in range(7):
                day = today - timedelta(days=offset)
                path = f'/lkml/{day.year}/{day.month}/{day.day}'
                index = fetch_archive(path, 300 if offset < 2 else 86400)
                stale = stale or index['stale']
                for row in index['messages']:
                    if is_linus(row['author']): candidates[row['id']] = row
            threads = {}
            for row in sorted(candidates.values(), key=lambda m: tuple(map(int,m['id'].split('/')[2:])), reverse=True)[:100]:
                message = fetch_archive(row['id'], 300)
                stale = stale or message['stale']
                if not is_linus(message['author']): continue
                root = message.get('thread_root', message['id'])
                # Root links identify conversations, even when subjects change.
                if root not in threads:
                    threads[root] = {k: message[k] for k in ('id','subject','author')}
            result = {'messages':list(threads.values()), 'fetched':time.time(),
                      'stale':stale, 'source':'https://lkml.org/lkml/last100'}
            if not stale: key.write_text(json.dumps(result))
            return result
        except Exception:
            if cached: return {**cached, 'stale':True}
            raise

def is_release_or_pull(subject):
    # Only announcement/request headers, not every reply or patch mentioning a release.
    return bool(re.match(r'^\[(?:GIT[ -])?PULL(?:\s[^]]*)?\]',subject,re.I) or
                re.fullmatch(r'Linux \d+\.\d+(?:\.\d+)?(?:-rc\d+)?',subject.strip(),re.I))

def build_releases_feed():
    rows={}; stale=False; fetched=time.time()
    today=datetime.now(timezone.utc).date()
    for offset in range(7):
        day=today-timedelta(days=offset)
        index=fetch_archive(f'/lkml/{day.year}/{day.month}/{day.day}',300 if offset<2 else 86400)
        stale=stale or index['stale']; fetched=min(fetched,index['fetched'])
        for row in index['messages']:
            if is_release_or_pull(row['subject']): rows[row['id']]=row
    return {'messages':sorted(rows.values(),key=lambda m:tuple(map(int,m['id'].split('/')[2:])),reverse=True)[:100],
            'fetched':fetched if stale else time.time(), 'stale':stale,'source':'https://lkml.org/lkml/last100'}

def releases_feed():
    key=CACHE / 'releases-feed.json'
    with cache_lock(key):
        cached=json.loads(key.read_text()) if key.exists() else None
        if cached and time.time()-cached['fetched']<300: return cached
        try:
            result=build_releases_feed()
            if not result['stale']: key.write_text(json.dumps(result))
            return result
        except Exception:
            if cached: return {**cached,'stale':True}
            raise

def sender_name(value):
    return value.split('<',1)[0].strip().strip('"')

def sender_profile(name, source="lkml"):
    name=sender_name(name)
    # Only use public archive metadata already retrieved for this reader.
    latest=fetch_archive(SOURCES[source]['index'],300,source)['messages']
    saved=[]
    for path in CACHE.glob(source+'_*.json'):
        try:
            record=json.loads(path.read_text())
            if 'id' in record: saved.append(record)
        except (OSError, ValueError): continue
    matches={}; addresses=set()
    for m in [*latest,*saved]:
        if sender_name(m.get('author','')).casefold()!=name.casefold(): continue
        matches[m['id']]={k:m[k] for k in ('id','subject','author')}
        address=re.search(r'<([^<>\s]+@[^<>\s]+)>',m['author'])
        if address and '...' not in address.group(1) and '…' not in address.group(1): addresses.add(address.group(1))
    ordered=sorted(matches.values(),key=lambda m:m['id'] if SOURCES[source].get('kind')=='atom' else tuple(map(int,m['id'].split('/')[2:])),reverse=True)
    return {'name':name,'addresses':sorted(addresses),'messages':ordered}

def theme():
    fallback = {'name': 'Ethereal', 'colors': {}}
    if os.environ.get('KERNEL_INBOX_THEME', 'auto') == 'default':
        return fallback
    base=Path.home()/'.local/state/omarchy/current'
    try:
        colors=tomllib.loads((base/'theme/colors.toml').read_text())
        return {'name':(base/'theme.name').read_text().strip(),'colors':{k:v for k,v in colors.items() if isinstance(v,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',v)}}
    except (OSError, ValueError):
        return fallback
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'dist/client'),**kw)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        super().end_headers()
    def do_GET(self):
        if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'): self.send_error(403); return
        u=urllib.parse.urlsplit(self.path)
        if not u.path.startswith('/api/'):
            return super().do_GET()
        params=urllib.parse.parse_qs(u.query)
        feed=params.get('list',['lkml'])[0]
        source='lkml' if feed in ('linus','releases') else feed
        if source not in SOURCES: self.send_error(400); return
        try:
            if u.path=='/api/theme': data=theme()
            elif u.path=='/api/feed': data=custom_feed(params.get('url',[''])[0])
            elif u.path=='/api/messages': data=linus_feed() if feed=='linus' else releases_feed() if feed=='releases' else fetch_archive(SOURCES[source]['index'],300,source)
            elif u.path=='/api/sender':
                name=urllib.parse.parse_qs(u.query).get('name',[''])[0]
                if not sender_name(name) or len(name)>300: self.send_error(400); return
                data=sender_profile(name,source)
            elif u.path=='/api/message':
                mid=urllib.parse.parse_qs(u.query).get('id',[''])[0]
                if not valid_id(mid,source): self.send_error(400); return
                data=fetch_archive(mid,300 if feed=='linus' else 86400,source)
            else: self.send_error(404); return
            status=200
        except ValueError as error:
            data={'error':str(error) if u.path=='/api/feed' else 'Invalid archive response.'}; status=400
        except Exception:
            data={'error':'The archive could not be reached. Please try refreshing in a moment.'}; status=502
        body=json.dumps(data).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=os.environ.get('KERNEL_INBOX_PORT', '8765'))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    if not (ROOT / 'dist/client/index.html').is_file():
        parser.error('frontend is missing; run npm ci and npm run build first')
    try:
        httpd = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError as error:
        parser.exit(1, f'Unable to start Kernel Inbox: {error}\n')
    print(f'Kernel Inbox: http://127.0.0.1:{args.port}', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == '__main__':
    main()
