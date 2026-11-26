"""Marca lida por script: tokens DTCG, fontes locais e símbolo. Nenhum valor de marca digitado aqui."""
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageFont

from . import CFG, RAIZ, caminho, ler_json, midia, rodar

FONTES = RAIZ / "assets/fonts"
# Papel tipográfico → arquivo (DESIGN.md §4.2 e SOCIAL.md §4). Variáveis: o peso vira eixo wght.
ARQUIVOS = {
    "titulo": ("Montserrat[wght].ttf", "Montserrat"),
    "corpo": ("SourceSans3[wght].ttf", "Source Sans 3"),
    "dado": ({400: "IBMPlexMono-Regular.ttf", 700: "IBMPlexMono-Bold.ttf"}, "IBM Plex Mono"),
}


@lru_cache(maxsize=None)
def tokens():
    return ler_json(caminho("marca") / "tokens/syntaxis.tokens.json")


def valor(chave):
    """Valor de um token por caminho com pontos ('social.type.body'), resolvendo aliases {a.b}."""
    no = tokens()
    for parte in chave.split("."):
        no = no[parte]
    v = no["$value"] if isinstance(no, dict) else no
    if isinstance(v, str) and (m := re.fullmatch(r"\{(.+)\}", v)):
        return valor(m[1])
    return v


def px(chave):
    return float(str(valor(chave)).removesuffix("px"))


def cor(chave):
    """Hex do token → tupla RGB."""
    h = valor(chave).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def versao_tokens():
    return tokens()["$extensions"]["br.com.syntaxis"]["version"]


def zona_segura(perfil=None):
    """Retângulo seguro (x0, y0, x1, y1) do 9:16. 'organico' vem dos tokens; 'anuncio' é a interseção."""
    perfil = perfil or CFG["zona_segura"]["padrao"]
    W, H = px("social.format.vertical.width"), px("social.format.vertical.height")
    z = [px("social.safeZone.margin"), px("social.safeZone.verticalTop"),
         W - px("social.safeZone.verticalRight"), H - px("social.safeZone.verticalBottom")]
    if perfil == "anuncio":
        a = CFG["zona_segura"]["anuncio"]
        z = [max(z[0], W * a["lateral_pct"] / 100), max(z[1], H * a["topo_pct"] / 100),
             min(z[2], W * (1 - a["lateral_pct"] / 100)), min(z[3], H * (1 - a["base_pct"] / 100))]
    return tuple(round(v) for v in z)


@lru_cache(maxsize=None)
def fonte(papel, peso, tamanho):
    arquivo, _ = ARQUIVOS[papel]
    if isinstance(arquivo, dict):
        arquivo = arquivo[min(arquivo, key=lambda p: abs(p - peso))]
    f = ImageFont.truetype(str(FONTES / arquivo), round(tamanho))
    if "[" in arquivo:
        f.set_variation_by_axes([peso])
    return f


def conferir_fontes():
    """Lista de problemas: arquivo ausente ou família diferente da prevista na marca."""
    erros = []
    for papel, (arquivo, familia) in ARQUIVOS.items():
        for a in (arquivo.values() if isinstance(arquivo, dict) else [arquivo]):
            p = FONTES / a
            if not p.exists():
                erros.append(f"fonte ausente: assets/fonts/{a} (rode scripts/baixar_fontes.py)")
            elif ImageFont.truetype(str(p), 20).getname()[0] != familia:
                erros.append(f"{a}: família {ImageFont.truetype(str(p), 20).getname()[0]!r}, esperada {familia!r}")
    return erros


@lru_cache(maxsize=None)
def simbolo(fundo_escuro=True):
    """Símbolo rasterizado do master SVG (LOGO/README.md), com o glifo de 3 módulos da banda."""
    glifo = 3 * px("social.band.glyphModule")
    caixa = round(glifo / 0.57)  # o glifo ocupa 57% da caixa (SOCIAL.md §3; LOGO/README.md)
    nome = "symbol-master-lime.svg" if fundo_escuro else "symbol-master.svg"
    destino = midia("_cache") / f"{Path(nome).stem}-{caixa}.png"
    if not destino.exists():
        # largura e altura juntas: só -width deixa o librsvg com a altura padrão e o glifo encolhe
        rodar(["ffmpeg", "-y", "-v", "error", "-width", caixa * 4, "-height", caixa * 4, "-keep_ar", 1,
               "-i", caminho("marca") / "LOGO" / nome,
               "-vf", f"scale={caixa}:-1:flags=lanczos", destino])
    return Image.open(destino).convert("RGBA")
