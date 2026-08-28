# -*- coding: utf-8 -*-
"""
WatchPlayer (v1.watchplay.shop) - Scraper MegaSource para Stremio/Nuvio.

Fluxo Corrigido:
  1. Recebe IMDb ID (ex: "tt1877830") -> Consulta Cinemeta -> Pega Título em PT-BR
  2. Busca Título no WatchPlayer -> Obtém a Slug/ID real no site
  3. Filme: GET /movie/{slug} -> Extrai video_id -> API getPlayer -> HLS Stream
  4. Série: GET /tvshow/{slug} -> Extrai contentid do episódio -> API getOptions -> API getPlayer -> HLS Stream

Compatível 100% com Stdlib (sem bibliotecas externas).
"""

import json
import re
import urllib.parse
import urllib.request

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0.0.0 Safari/537.36")

FALLBACK_DOMAIN = "https://v1.watchplay.shop"
API_URL = FALLBACK_DOMAIN + "/api"
TIMEOUT = 12

STREAM_PATTERN = re.compile(r"\.m3u8|\.mp4|/hls/", re.I)


def _request(url, data=None, timeout=TIMEOUT):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Origin"] = FALLBACK_DOMAIN
        headers["Referer"] = FALLBACK_DOMAIN + "/"
    req = urllib.request.Request(
        url, data=data, headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _get_meta_from_cinemeta(imdb_id, media_type):
    """Converte IMDb ID para título em Português usando a API pública do Cinemeta."""
    try:
        clean_id = imdb_id.split(":")[0]
        type_path = "series" if media_type == "series" else "movie"
        url = "https://v3-cinemeta.strem.fun/meta/%s/%s.json" % (type_path, clean_id)
        
        req = urllib.request.Request(url, headers={"Accept-Language": "pt-BR,pt", "User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                meta = data.get("meta", {})
                return meta.get("name"), meta.get("year")
    except Exception:
        pass
    return None, None


def _search_item(title, media_type):
    """Busca o título no WatchPlayer e retorna a slug/ID interna do site."""
    if not title:
        return None
        
    query = urllib.parse.quote(title)
    search_url = "%s/search?q=%s" % (FALLBACK_DOMAIN, query)
    html = _request(search_url)
    
    if not html:
        return None

    # Procura por links de filmes ou séries na página de resultados
    prefix = "/movie/" if media_type == "movie" else "/tvshow/"
    pattern = re.compile(r'href=["\']' + re.escape(FALLBACK_DOMAIN) + r'?' + re.escape(prefix) + r'([^"\']+)["\']')
    
    matches = pattern.findall(html)
    if matches:
        return matches[0].strip("/")
        
    # Fallback para animes se for série
    if media_type == "series":
        anime_pattern = re.compile(r'href=["\']' + re.escape(FALLBACK_DOMAIN) + r'?/anime/([^"\']+)["\']')
        anime_matches = anime_pattern.findall(html)
        if anime_matches:
            return "anime:" + anime_matches[0].strip("/")

    return None


def _api(action, **params):
    body = urllib.parse.urlencode({"action": action}, doseq=True)
    for key, value in params.items():
        body += "&" + urllib.parse.urlencode({key: value})
    raw = _request(API_URL, data=body.encode("utf-8"))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _get_player(video_id):
    """Chama getPlayer e devolve a URL HLS/MP4 ou None."""
    res = _api("getPlayer", video_id=video_id)
    if not res:
        return None
    data = res.get("data") or {}
    url = data.get("video_url") or data.get("url")
    if not url or not STREAM_PATTERN.search(url):
        return None
    return url


def _get_options(contentid):
    res = _api("getOptions", contentid=contentid)
    if not res:
        return []
    return (res.get("data") or {}).get("options") or []


def _label_for_type(typ, index):
    if typ == 1:
        return "Dublado"
    if typ == 2:
        return "Legendado"
    return "Opcao %d" % (index + 1)


def _movie_candidates(html):
    candidates = []
    default_type = None
    m = re.search(r'<div class="select_languages">(.*?)</div>', html, re.S)
    if m:
        text = m.group(1)
        if "Dublado" in text:
            default_type = 1
        elif "Legendado" in text:
            default_type = 2

    segments = re.split(r'<div class="players_select_items', html)
    for seg in segments[1:]:
        gt = seg.find(">")
        attrs = seg[:gt] if gt != -1 else ""
        mt = re.search(r'data-target="(\d+)"', attrs)
        group_type = int(mt.group(1)) if mt else default_type
        body = seg[gt + 1:] if gt != -1 else seg
        for vid in re.finditer(r'player_select_item"\s+data-id="(\d+)"', body):
            candidates.append((int(vid.group(1)), group_type))
    if not candidates:
        for vid in re.finditer(r'player_select_item"\s+data-id="(\d+)"', html):
            candidates.append((int(vid.group(1)), default_type))
    return candidates


def _episode_match(html, season, episode):
    first = None
    for m in re.finditer(
        r'episodeOption[^>]*data-contentid="(\d+)"[^>]*data-season="(\d+)"'
        r'[^>]*data-episode="(\d+)"',
        html,
    ):
        cid, s, e = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if first is None:
            first = (cid, s, e)
        if s == season and e == episode:
            return (cid, s, e)
    if season is None or episode is None:
        return first
    return None


def _build_stream(url, title):
    return {
        "title": title,
        "url": url,
        "behaviorHints": {"notMyMetadata": True},
        "proxyHeaders": {
            "request": {
                "User-Agent": USER_AGENT,
                "Origin": FALLBACK_DOMAIN,
                "Referer": FALLBACK_DOMAIN + "/",
            }
        },
    }


def get_streams(media_type, media_id, config=None):
    config = config or {}
    media_id = urllib.parse.unquote(media_id or "")
    parts = [p.strip() for p in media_id.split(":")]
    if not parts or not parts[0]:
        return []

    imdb_id = parts[0]

    try:
        season = int(parts[1]) if len(parts) > 1 else None
        episode = int(parts[2]) if len(parts) > 2 else None
    except ValueError:
        season, episode = None, None

    if config.get("season") is not None:
        season = int(config["season"])
    if config.get("episode") is not None:
        episode = int(config["episode"])

    # 1. Pega o nome do título traduzido via Cinemeta
    title_pt, year = _get_meta_from_cinemeta(imdb_id, media_type)
    if not title_pt:
        return []

    # 2. Localiza a slug real da postagem no WatchPlayer
    site_slug = _search_item(title_pt, media_type)
    if not site_slug:
        return []

    streams = []
    seen = set()

    # Fluxo para Filmes
    if media_type == "movie":
        html = _request("%s/movie/%s" % (FALLBACK_DOMAIN, site_slug))
        if not html:
            return []
        for index, (video_id, typ) in enumerate(_movie_candidates(html)):
            url = _get_player(video_id)
            if not url or url in seen:
                continue
            seen.add(url)
            streams.append(_build_stream(
                url, "WatchPlayer • %s" % _label_for_type(typ, index),
            ))
        return streams

    # Fluxo para Séries e Animes
    path = "anime" if site_slug.startswith("anime:") else "tvshow"
    clean_slug = site_slug.replace("anime:", "")

    html = _request("%s/%s/%s" % (FALLBACK_DOMAIN, path, clean_slug))
    if not html or "episodeOption" not in html:
        return []

    match = _episode_match(html, season, episode)
    if not match:
        return []
    contentid, s, e = match

    for index, option in enumerate(_get_options(contentid)):
        video_id = option.get("ID")
        typ = int(option.get("type") or 0)
        if not video_id:
            continue
        url = _get_player(video_id)
        if not url or url in seen:
            continue
        seen.add(url)
        streams.append(_build_stream(
            url,
            "WatchPlayer • S%de%d • %s" % (s, e, _label_for_type(typ, index)),
        ))
    return streams


if __name__ == "__main__":
    # Teste rápido local com 'The Batman' (tt1877830)
    print(get_streams("movie", "tt1877830"))
