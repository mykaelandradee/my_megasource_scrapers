import re
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://superflixapi.dev"  # Domínio do Superflix/API

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL
}

def get_meta_from_cinemeta(imdb_id: str, media_type: str) -> tuple[str, str]:
    """Converte o IMDb ID no título traduzido em Português."""
    try:
        clean_id = imdb_id.split(":")[0]
        type_path = "series" if media_type == "series" else "movie"
        url = f"https://v3-cinemeta.strem.fun/meta/{type_path}/{clean_id}.json"
        
        res = requests.get(url, headers={"Accept-Language": "pt-BR,pt"}, timeout=5)
        if res.status_code == 200:
            meta = res.json().get("meta", {})
            return meta.get("name"), str(meta.get("year")) if meta.get("year") else None
    except Exception:
        pass
    return None, None

def get_streams(media_type: str, media_id: str, config: dict = None) -> list:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Metadados do Cinemeta
    title, year = get_meta_from_cinemeta(media_id, media_type)
    if not title:
        return results

    try:
        # 2. Busca no Superflix
        search_url = f"{BASE_URL}/?s={quote_plus(title)}"
        res = session.get(search_url, timeout=8)
        if res.status_code != 200:
            return results

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select("article a[href], .result-item a[href], h2 a[href]")
        post_urls = list(dict.fromkeys([a["href"] for a in items if BASE_URL in a.get("href", "")]))[:2]

        for post_url in post_urls:
            post_res = session.get(post_url, timeout=8)
            if post_res.status_code != 200:
                continue

            html = post_res.text
            post_soup = BeautifulSoup(html, "html.parser")

            # 3. Pega o ID do Post do WordPress (padrão Dooplay do script da Bruna)
            post_id_match = re.search(r'data-id=["\'](\d+)["\']', html) or re.search(r'post-(\d+)', html)
            if not post_id_match:
                continue
            
            post_id = post_id_match.group(1)

            # Extrai os botões/opções de player
            player_options = post_soup.select("li.dooplay_player_option, option[data-type]")

            for option in player_options:
                nump = option.get("data-nump") or option.get("data-option")
                type_attr = option.get("data-type", "movie")
                server_name = option.text.strip() or "Superflix Player"

                if nump:
                    # Chamada AJAX idêntica ao scraper da Bruna
                    payload = {
                        "action": "doo_player_ajax",
                        "post": post_id,
                        "nump": nump,
                        "type": type_attr
                    }
                    
                    ajax_res = session.post(f"{BASE_URL}/wp-admin/admin-ajax.php", data=payload, timeout=6)
                    if ajax_res.status_code == 200:
                        try:
                            embed_html = ajax_res.json().get("embed_url", "")
                        except Exception:
                            embed_html = ajax_res.text

                        # Extrai a URL contida no iframe do embed
                        iframe_match = re.search(r'src=["\']([^"\']+)["\']', embed_html)
                        stream_url = iframe_match.group(1) if iframe_match else embed_html

                        if stream_url.startswith("//"):
                            stream_url = "https:" + stream_url

                        if stream_url and "http" in stream_url:
                            results.append({
                                "name": "Superflix",
                                "title": f"Superflix | {server_name}\n🎥 Stream Dublado/Nacional",
                                "url": stream_url,
                                "quality": "720p"
                            })

    except Exception as err:
        print(f"[Superflix Error]: {err}")

    return results

if __name__ == "__main__":
    print("--- Testando Scraper Superflix (Base Bruna Cristina) ---")
    res = get_streams("movie", "tt1877830", {})
    print(f"Total encontrado: {len(res)}")
    for item in res:
        print(item)
