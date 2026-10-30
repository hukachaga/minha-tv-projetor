#!/usr/bin/env python3
"""YouTube feed for Free My TV: new videos from your subscriptions, without Shorts or lives, newest first (or, with
"order": "score", the channels whose videos you like most first). Python 3 standard library only.

  ytfeed.py auth       once: sign in on your phone (Google's device code), keeps a refresh token
  ytfeed.py refresh    writes /var/lib/ytfeed/public/feed.json (the systemd timer runs it every 5 minutes)
  ytfeed.py status     what the last refresh found

Files: /etc/ytfeed/client_secret.json (an OAuth client of type "TVs and Limited Input devices", from Google Cloud),
/etc/ytfeed/config.json (optional, see DEFAULTS), /var/lib/ytfeed/token.json (written by auth, 0600).
"""
import concurrent.futures
import http.client
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ETC = '/etc/ytfeed'
VAR = '/var/lib/ytfeed'
PUBLIC = os.path.join(VAR, 'public')
TOKEN = os.path.join(VAR, 'token.json')
CACHE = os.path.join(VAR, 'cache.json')
SCOPE = 'https://www.googleapis.com/auth/youtube.readonly'
API = 'https://www.googleapis.com/youtube/v3'
DEFAULTS = {
    'days': 10,             # videos older than this are left out
    'max_items': 30,        # how many go in the feed
    'order': 'recent',      # 'recent': newest first; 'score': the channels you like most first, fading with age
    'per_channel': 0,       # at most this many from one channel; 0: no limit
    'short_max_seconds': 180,   # Shorts are at most 3 minutes: only those get the /shorts/ check
    'max_seconds': 7200,    # longer videos (mostly recordings of lives) are left out; 0 keeps them all
    'favorites': [],        # channel ids or names (part of it) that always rank higher
    'blocked': [],          # channel ids or names (part of it) never shown
    'half_life_hours': 48,  # how fast a video's score fades with age
}
NS = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
      'media': 'http://search.yahoo.com/mrss/'}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data, mode=0o644):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def client():
    c = load(os.path.join(ETC, 'client_secret.json'), None)
    if not c:
        sys.exit('Missing /etc/ytfeed/client_secret.json (OAuth client "TVs and Limited Input devices").')
    c = c.get('installed') or c.get('web') or c
    return c['client_id'], c['client_secret']


def post(url, fields):
    req = urllib.request.Request(url, urllib.parse.urlencode(fields).encode())
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def get_json(url, token=None):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token} if token else {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


# --- Sign-in (OAuth device flow) ---

def auth():
    cid, secret = client()
    d = post('https://oauth2.googleapis.com/device/code', {'client_id': cid, 'scope': SCOPE})
    if 'device_code' not in d:
        sys.exit('Google refused: %s' % d)
    print('\nOn your phone or computer, open  %s\nand type the code:  %s\n' % (d['verification_url'], d['user_code']))
    wait = d.get('interval', 5)
    deadline = time.time() + d.get('expires_in', 1800)
    while time.time() < deadline:
        time.sleep(wait)
        t = post('https://oauth2.googleapis.com/token', {
            'client_id': cid, 'client_secret': secret, 'device_code': d['device_code'],
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'})
        if 'refresh_token' in t:
            os.makedirs(VAR, exist_ok=True)
            save(TOKEN, {'refresh_token': t['refresh_token']}, 0o600)
            print('Signed in. Now: ytfeed.py refresh')
            return
        err = t.get('error')
        if err == 'slow_down':
            wait += 5
        elif err != 'authorization_pending':
            sys.exit('Sign-in failed: %s' % t)
    sys.exit('The code expired: run auth again.')


def access_token():
    tok = load(TOKEN, None)
    if not tok:
        sys.exit('Not signed in: run  ytfeed.py auth')
    cid, secret = client()
    t = post('https://oauth2.googleapis.com/token', {
        'client_id': cid, 'client_secret': secret, 'refresh_token': tok['refresh_token'],
        'grant_type': 'refresh_token'})
    if 'access_token' not in t:
        sys.exit('Could not refresh the sign-in (run auth again): %s' % t)
    return t['access_token']


# --- YouTube ---

def pages(url, token, limit=40):
    """Every item of a paged list (each page costs 1 unit of the 10,000 a day)."""
    page = ''
    for _ in range(limit):
        d = get_json(url + ('&pageToken=' + page if page else ''), token)
        yield from d.get('items', [])
        page = d.get('nextPageToken')
        if not page:
            return


def subscriptions(token):
    return {s['snippet']['resourceId']['channelId']: s['snippet']['title']
            for s in pages(API + '/subscriptions?part=snippet&mine=true&maxResults=50', token)}


def liked_channels(token):
    """How many of your last ~200 liked videos come from each channel: the channels you watch most."""
    count = {}
    for v in pages(API + '/videos?part=snippet&myRating=like&maxResults=50', token, limit=4):
        ch = v['snippet']['channelId']
        count[ch] = count.get(ch, 0) + 1
    return count


def rss(channel):
    """The channel's latest 15 uploads from its public feed (free: no API quota)."""
    url = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + channel
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            root = ET.parse(r).getroot()
    except Exception as e:
        log('rss', channel, e)
        return []
    out = []
    for e in root.findall('a:entry', NS):
        link = e.find('a:link', NS)
        out.append({'id': e.findtext('yt:videoId', '', NS), 'channel_id': channel,
                    'title': e.findtext('a:title', '', NS), 'published': e.findtext('a:published', '', NS),
                    'href': link.get('href', '') if link is not None else ''})
    return out


def seconds(iso):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def details(ids, token):
    out = {}
    for i in range(0, len(ids), 50):
        d = get_json(API + '/videos?part=snippet,contentDetails&id=' + ','.join(ids[i:i + 50]), token)
        for v in d.get('items', []):
            out[v['id']] = v
    return out


def is_short(video_id):
    """YouTube answers /shorts/<id> with the Short itself, and redirects to /watch for any other video."""
    try:
        c = http.client.HTTPSConnection('www.youtube.com', timeout=15)
        c.request('HEAD', '/shorts/' + video_id, headers={'User-Agent': 'Mozilla/5.0'})
        status = c.getresponse().status
        c.close()
        return status == 200
    except Exception:
        return False


def thumb(snippet, video_id):
    t = snippet.get('thumbnails', {})
    for k in ('maxres', 'standard', 'high'):
        if k in t:
            return t[k]['url']
    return 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % video_id


def matches(names, channel_id, title):
    t = title.lower()
    return any(n == channel_id or (n and n.lower() in t) for n in names)


# --- The feed ---

def refresh():
    cfg = dict(DEFAULTS, **load(os.path.join(ETC, 'config.json'), {}))
    token = access_token()
    cache = load(CACHE, {})
    now = time.time()
    if now - cache.get('subs_at', 0) > 12 * 3600 or not cache.get('subs'):
        cache['subs'] = subscriptions(token)
        cache['likes'] = liked_channels(token)
        cache['subs_at'] = now
        log('subscriptions:', len(cache['subs']), 'liked channels:', len(cache['likes']))
    subs, likes = cache['subs'], cache['likes']
    channels = [c for c in subs if not matches(cfg['blocked'], c, subs[c])]

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        entries = [e for lst in pool.map(rss, channels) for e in lst]
    oldest = now - cfg['days'] * 86400
    fresh = []
    for e in entries:
        try:
            at = datetime.fromisoformat(e['published']).timestamp()
        except ValueError:
            continue
        if at >= oldest and '/shorts/' not in e['href']:
            e['at'] = at
            fresh.append(e)

    shorts = cache.setdefault('shorts', {})
    info = details([e['id'] for e in fresh], token)
    candidates = []
    for e in fresh:
        v = info.get(e['id'])
        if not v or v['snippet'].get('liveBroadcastContent', 'none') != 'none':
            continue    # removed, private, live or upcoming
        dur = seconds(v['contentDetails'].get('duration'))
        if dur == 0:
            continue    # a finished live without a duration yet, or a premiere
        if cfg['max_seconds'] and dur > cfg['max_seconds']:
            continue    # too long: a live's recording
        e.update(duration=dur, thumb=thumb(v['snippet'], e['id']))
        candidates.append(e)
    unknown = [e['id'] for e in candidates if e['duration'] <= cfg['short_max_seconds'] and e['id'] not in shorts]
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        for vid, short in zip(unknown, pool.map(is_short, unknown)):
            shorts[vid] = short
    candidates = [e for e in candidates if not shorts.get(e['id'])]

    def score(e):
        ch = e['channel_id']
        weight = 1 + math.log1p(likes.get(ch, 0)) + (3 if matches(cfg['favorites'], ch, subs.get(ch, '')) else 0)
        return weight * 0.5 ** ((now - e['at']) / 3600 / cfg['half_life_hours'])

    per, items = {}, []
    for e in sorted(candidates, key=score if cfg['order'] == 'score' else lambda e: e['at'], reverse=True):
        ch = e['channel_id']
        if cfg['per_channel'] and per.get(ch, 0) >= cfg['per_channel']:
            continue
        per[ch] = per.get(ch, 0) + 1
        items.append({'id': e['id'], 'title': e['title'], 'channel': subs.get(ch, ''), 'published': e['published'],
                      'duration': e['duration'], 'thumb': e['thumb']})
        if len(items) >= cfg['max_items']:
            break

    keep = {e['id'] for e in fresh}
    cache['shorts'] = {k: v for k, v in shorts.items() if k in keep}
    cache['last'] = {'at': now, 'channels': len(channels), 'recent': len(fresh), 'kept': len(items),
                     'shorts_dropped': sum(1 for e in fresh if cache['shorts'].get(e['id']) or '/shorts/' in e['href'])}
    save(CACHE, cache, 0o600)
    os.makedirs(PUBLIC, exist_ok=True)
    save(os.path.join(PUBLIC, 'feed.json'), {'updated': datetime.now(timezone.utc).isoformat(), 'items': items})
    log('feed:', cache['last'])


def status():
    last = load(CACHE, {}).get('last')
    print(json.dumps(last, indent=1) if last else 'No refresh yet.')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'auth': auth, 'refresh': refresh, 'status': status}.get(cmd, lambda: sys.exit(__doc__))()
