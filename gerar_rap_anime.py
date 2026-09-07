import os
import json
import re
import time
import random
import string
import unicodedata
from pathlib import Path
import urllib.request
import yt_dlp
import imageio_ffmpeg

# --- CORES PARA O TERMINAL ---
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

# --- CONFIGURAÇÃO DO GITHUB DO USUÁRIO ---
GITHUB_USER = "escritor3"
GITHUB_REPO = "rap_anime"
GITHUB_BRANCH = "main"

RAW_BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"

# --- CONFIGURAÇÃO DE DIRETÓRIOS LOCAIS ---
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR / "rap_anime"
AUDIO_DIR = PROJECT_DIR / "audio"
CAPAS_DIR = PROJECT_DIR / "capas"

PLAYLIST_JSON = PROJECT_DIR / "playlist.json"
HISTORICO_TXT = PROJECT_DIR / "historico_downloads.txt"

QUANTIDADE_TOTAL_DESEJADA = 100
DURACAO_MIN_SEGUNDOS = 90
DURACAO_MAX_SEGUNDOS = 480  # Máximo de 8 minutos
TAMANHO_MAX_MB = 15.0       # Limite ajustado para faixas de até 8 min

# Termos de Busca para Rap de Anime, Mangá e Manhwa
TERMOS_BUSCA_GEEK = [
    # Mangás e Manhwas
    "rap de manga studio audio",
    "rap de manhwa studio audio",
    "rap de berserk studio audio",
    "rap de vagabond studio audio",
    "rap de kagurabachi studio",
    "rap de sakamoto days studio",
    "rap de solo leveling studio",
    "rap de chainsaw man manga audio",
    "rap de jujutsu kaisen manga audio",
    "rap de blue lock manga studio",
    
    # Animes e Cultura Geek Geral
    "rap de anime studio audio oficial",
    "geek rap audio oficial",
    "rap nerd audio oficial",
    "trap geek audio oficial",
    
    # Artistas Relevantes
    "m4rkim audio oficial",
    "anirap audio oficial",
    "mhrap studio audio",
    "7 minutoz studio audio",
    "player tauz audio",
    "fabvl audio",
    "henran rap studio",
    "chrono rap audio oficial"
]

SUFIXOS_VARIACAO = [
    "audio oficial", "official audio", "studio", "prod", 
    "2024", "2025", "2026", "single"
] + list(string.ascii_lowercase)

PALAVRAS_BLOQUEADAS = [
    "ao vivo", "live", "show completo", "full album", "album completo", 
    "coletanea", "dvd", "festival", "set", "dj set", "non stop", "as melhores",
    "react", "reagindo", "bastidores", "making of", "vlog", "podcast"
]

def obter_caminho_ffmpeg():
    # 1. Procura o ffmpeg.exe na mesma pasta do script
    local_ffmpeg = BASE_DIR / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    
    # 2. Tenta pegar pelo pacote imageio_ffmpeg
    try:
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    return None

def normalizar_para_comparacao(texto):
    nfkd = unicodedata.normalize('NFKD', texto)
    sem_acentos = u"".join([c for c in nfkd if not unicodedata.combining(c)]).lower()
    return re.sub(r'[^a-zA-Z0-9]', '', sem_acentos)

def sanitizar_nome(nome):
    nome_limpo = re.sub(r'[\\/*?:"<>|#%&]', '', nome)
    return " ".join(nome_limpo.split()).strip()

def contem_palavras_bloqueadas(titulo):
    titulo_lower = titulo.lower()
    return any(palavra in titulo_lower for palavra in PALAVRAS_BLOQUEADAS)

def carregar_historico():
    ids = set()
    titulos = set()
    
    if HISTORICO_TXT.exists():
        with open(HISTORICO_TXT, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) >= 2:
                    ids.add(parts[0])
                    titulos.add(normalizar_para_comparacao(parts[1]))
                    
    if PLAYLIST_JSON.exists():
        try:
            with open(PLAYLIST_JSON, "r", encoding="utf-8") as f:
                playlist_data = json.load(f)
                for item in playlist_data:
                    if "titulo" in item:
                        titulos.add(normalizar_para_comparacao(item["titulo"]))
        except Exception:
            pass

    return ids, titulos

def registrar_historico(vid_id, titulo, genero, url_publica):
    HISTORICO_TXT.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORICO_TXT, "a", encoding="utf-8") as f:
        f.write(f"{vid_id}|{titulo}|{genero}|{url_publica}\n")

def criar_arquivos_auxiliares():
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    
    rap_anime_js = PROJECT_DIR / "rap_anime.js"
    content_js = f"""// Extensão "Rap de Anime e Mangá" para FreeBeat
const PLAYLIST_URL = '{RAW_BASE_URL}/playlist.json';

module.exports = {{
  id: 'rap_anime_repo',
  name: 'Rap de Anime & Mangá',
  version: '1.0.0',
  hasCatalog: true,

  async getCatalog(api) {{
    const data = await api.httpGetJson(PLAYLIST_URL);
    return api.normalizeSongs(data);
  }},

  async search(query, api) {{
    const data = await api.httpGetJson(PLAYLIST_URL);
    const songs = api.normalizeSongs(data);
    const q = query.toLowerCase();
    return songs.filter(
      (s) =>
        s.titulo.toLowerCase().includes(q) ||
        (s.artista && s.artista.toLowerCase().includes(q)) ||
        (s.genero && s.genero.toLowerCase().includes(q))
    );
  }},
}};
"""
    with open(rap_anime_js, "w", encoding="utf-8") as f:
        f.write(content_js)

    registry_json = PROJECT_DIR / "registry.json"
    content_registry = [
        {
            "id": "rap_anime_repo",
            "name": "Rap de Anime & Mangá",
            "version": "1.0.0",
            "description": "Playlist de rap de animes e mangás mantida por escritor3",
            "jsUrl": f"{RAW_BASE_URL}/rap_anime.js"
        }
    ]
    with open(registry_json, "w", encoding="utf-8") as f:
        json.dump(content_registry, f, ensure_ascii=False, indent=2)

def baixar_e_salvar_capa(thumbnail_url: str, nome_arquivo: str) -> str:
    if not thumbnail_url:
        return ""
    
    caminho_capa = CAPAS_DIR / f"{nome_arquivo}.jpg"
    try:
        req = urllib.request.Request(
            thumbnail_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(caminho_capa, 'wb') as out_file:
            out_file.write(response.read())
            
        return f"{RAW_BASE_URL}/capas/{nome_arquivo}.jpg"
    except Exception as e:
        print(f"  {YELLOW}[!] Erro ao salvar capa: {e}{RESET}")
        return ""

def buscar_e_baixar_rap_anime():
    ffmpeg_loc = obter_caminho_ffmpeg()
    
    if not ffmpeg_loc:
        print(f"{RED}✖ ERRO CRÍTICO: O arquivo ffmpeg.exe não foi encontrado na pasta.{RESET}")
        return

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    CAPAS_DIR.mkdir(parents=True, exist_ok=True)
    criar_arquivos_auxiliares()

    ids_salvos, titulos_salvos = carregar_historico()
    
    playlist_data = []
    if PLAYLIST_JSON.exists():
        try:
            with open(PLAYLIST_JSON, "r", encoding="utf-8") as f:
                playlist_data = json.load(f)
        except Exception:
            playlist_data = []

    print(f"{CYAN}=== GERADOR DE REPOSITÓRIO GITHUB (FFMPEG ENCONTRADO) ==={RESET}\n")

    genero = "rap_anime"
    baixadas = len(playlist_data)
    tentativas_sem_sucesso = 0

    extractor_args_config = {
        'youtube': {
            'player_client': ['web', 'android'],
            'skip': ['hls', 'dash']
        }
    }

    while baixadas < QUANTIDADE_TOTAL_DESEJADA and tentativas_sem_sucesso < 40:
        termo_base = random.choice(TERMOS_BUSCA_GEEK)
        sufixo = random.choice(SUFIXOS_VARIACAO)
        termo_busca = f"{termo_base} {sufixo}"
        
        query = f"ytsearch25:{termo_busca}"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'ignoreerrors': True,
            'extractor_args': extractor_args_config
        }

        entries = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                if info and 'entries' in info:
                    entries = info['entries']
        except Exception:
            tentativas_sem_sucesso += 1
            continue

        se_baixou_algo_nesta_rodada = False

        for entry in entries:
            if not entry or baixadas >= QUANTIDADE_TOTAL_DESEJADA:
                break

            vid_id = entry.get('id')
            title_raw = entry.get('title', '')
            
            if contem_palavras_bloqueadas(title_raw):
                continue

            title_sanitizado = sanitizar_nome(title_raw)
            chave = normalizar_para_comparacao(title_sanitizado)

            if not vid_id or not title_sanitizado:
                continue

            if vid_id in ids_salvos or chave in titulos_salvos:
                continue

            nome_arquivo_base = f"musica_{baixadas + 1:03d}"
            output_mp3 = AUDIO_DIR / f"{nome_arquivo_base}.mp3"
            output_template = str(AUDIO_DIR / f"{nome_arquivo_base}.%(ext)s")

            ydl_dl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': ffmpeg_loc,
                'extractor_args': extractor_args_config,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'match_filter': yt_dlp.utils.match_filter_func(
                    f'duration >= {DURACAO_MIN_SEGUNDOS} & duration <= {DURACAO_MAX_SEGUNDOS} & !is_live & !was_live'
                ),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
            }

            try:
                print(f"  {GREEN}[+] Baixando e Convertendo ({baixadas + 1}/{QUANTIDADE_TOTAL_DESEJADA}):{RESET} '{title_sanitizado}'...")
                
                with yt_dlp.YoutubeDL(ydl_dl_opts) as ydl_dl:
                    info_meta = ydl_dl.extract_info(f"https://www.youtube.com/watch?v={vid_id}", download=True)
                    thumbnail_url = info_meta.get('thumbnail', '') if info_meta else ''
                    artista_extraido = info_meta.get('uploader', 'Desconhecido') if info_meta else 'Desconhecido'

                if output_mp3.exists():
                    tamanho_mb = round(output_mp3.stat().st_size / (1024 * 1024), 2)
                    
                    if tamanho_mb > TAMANHO_MAX_MB:
                        print(f"  {RED}[-] Descartando ({tamanho_mb} MB excede {TAMANHO_MAX_MB} MB):{RESET} '{title_sanitizado}'")
                        output_mp3.unlink()
                        continue

                    capa_url_github = baixar_e_salvar_capa(thumbnail_url, nome_arquivo_base)
                    audio_url_github = f"{RAW_BASE_URL}/audio/{nome_arquivo_base}.mp3"

                    playlist_data.append({
                        "id": f"rap_anime_{len(playlist_data) + 1:03d}",
                        "titulo": title_sanitizado,
                        "artista": artista_extraido.replace(" - Topic", "").strip(),
                        "genero": "rap_anime",
                        "url": audio_url_github,
                        "capa_url": capa_url_github
                    })

                    ids_salvos.add(vid_id)
                    titulos_salvos.add(chave)
                    registrar_historico(vid_id, title_sanitizado, genero, audio_url_github)
                    
                    baixadas += 1
                    se_baixou_algo_nesta_rodada = True
                    tentativas_sem_sucesso = 0
                    
                    time.sleep(1.2)

            except Exception as e:
                print(f"  {RED}[✖] Falha ao processar '{title_sanitizado}': {e}{RESET}")

        if not se_baixou_algo_nesta_rodada:
            tentativas_sem_sucesso += 1

    with open(PLAYLIST_JSON, "w", encoding="utf-8") as f:
        json.dump(playlist_data, f, ensure_ascii=False, indent=2)

    print(f"\n{GREEN}✔ Concluído! Todos os arquivos foram salvos como MP3 com áudio funcional.{RESET}")

if __name__ == "__main__":
    buscar_e_baixar_rap_anime()