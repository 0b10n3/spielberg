"""Etapa 6: legenda queimada em PNG (Pillow), um por bloco, mais o SRT como subproduto.

Decisão (docs/pesquisa.md): PNG em vez de ASS/libass. A caixa de cada bloco é medida com a mesma
fonte que desenha (sem diferença de métrica entre Pillow e libass) e a fonte variável da marca funciona
sem depender da busca de fontes do libass. Os PNGs entram no vídeo como uma única sequência (concat)."""
from PIL import Image

from . import CFG
from . import marca as M
from .cartoes import Tela, dimensoes, quebrar


def faixa(perfil=None):
    return tuple(CFG["legenda"]["faixa"][perfil or CFG["zona_segura"]["padrao"]])


def bloco(texto, destino):
    """PNG do bloco: texto Chalk sobre caixa Deep Forest translúcida, centrada na zona segura."""
    L = CFG["legenda"]
    W, H = dimensoes()
    x0, _, x1, _ = M.zona_segura()
    topo = faixa()[0]
    f = M.fonte(L["fonte"], L["peso"], L["tamanho"])
    pad = L["caixa_padding"]
    linhas = quebrar(texto, f, x1 - x0 - 2 * pad)  # mais linhas que o limite: o QA reprova pela caixa
    entre = f.size * L["entrelinha"]
    centro = (x0 + x1) / 2
    camada = Tela(W, H)
    larg = max(f.getlength(l) for l in linhas)
    alt = len(linhas) * entre
    caixa = [centro - larg / 2 - pad, topo, centro + larg / 2 + pad, topo + alt + 2 * pad]
    fundo = (*M.cor("color.neutral.deepForest"), round(255 * L["caixa_opacidade"]))
    camada.d.rectangle(caixa, fill=fundo)
    y = topo + pad
    for l in linhas:
        camada.linha(centro - f.getlength(l) / 2, y, l, f, M.cor("color.neutral.chalk"), tipo="legenda")
        y += entre
    camada.caixas.append({"tipo": "legenda-caixa", "texto": texto, "caixa": [round(v) for v in caixa]})
    camada.img.save(destino)
    return camada.caixas


def vazio(destino):
    W, H = dimensoes()
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(destino)


def concat(itens, duracao, pasta, nome):
    """Lista ffconcat de PNGs com duração: transparente nos intervalos, cada item no seu [ini, fim]."""
    vz = pasta / "vazio.png"
    if not vz.exists():
        vazio(vz)
    linhas, t = ["ffconcat version 1.0"], 0.0
    for it in sorted(itens, key=lambda i: i["ini"]):
        ini, fim = max(it["ini"], t), min(it["fim"], duracao)
        if fim - ini < 1 / 30:
            continue
        if ini - t > 0.001:
            linhas += [f"file '{vz}'", f"duration {ini - t:.3f}"]
        linhas += [f"file '{pasta / it['png']}'", f"duration {fim - ini:.3f}"]
        t = fim
    linhas += [f"file '{vz}'", f"duration {max(duracao - t, 0.04):.3f}", f"file '{vz}'"]
    destino = pasta / f"{nome}.ffconcat"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino


def srt(L, destino):
    def tc(s):
        ms = round(s * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    partes = [f"{i}\n{tc(b['ini'])} --> {tc(b['fim'])}\n{b['texto']}\n" for i, b in enumerate(L, 1)]
    destino.write_text("\n".join(partes), encoding="utf-8")
