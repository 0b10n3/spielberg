"""Etapa 5: cartões e capa em PNG 1080×1920 (Pillow), com a marca lida dos tokens. Cada texto desenhado
tem a caixa medida e registrada para o QA (zona segura e faixa da legenda)."""
import re

from PIL import Image, ImageDraw

from . import CFG
from . import marca as M

NUMERO = re.compile(r"^[−\-+~]?\s?(R\$\s?)?\d")
F = CFG["marca_fora_dos_tokens"]


def dimensoes():
    return int(M.px("social.format.vertical.width")), int(M.px("social.format.vertical.height"))


def paleta(escuro):
    return {"fundo": M.cor("color.neutral.deepForest" if escuro else "color.neutral.chalk"),
            "texto": M.cor("color.neutral.chalk" if escuro else "color.neutral.ink"),
            "eyebrow": M.cor("social.eyebrowOnDark" if escuro else "component.eyebrow.colorLight"),
            "hairline": M.cor("component.hairline.colorSocial")}


class Tela:
    """Camada RGBA que desenha texto e guarda a caixa medida de cada linha."""

    def __init__(self, w, h, fundo=None):
        self.img = Image.new("RGBA", (w, h), (*fundo, 255) if fundo else (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.caixas = []

    def linha(self, x, y, s, fonte, cor, tracking=0.0, tipo="texto"):
        if tracking:
            cx, x0, y0, x1, y1 = x, None, None, None, None
            for ch in s:
                b = self.d.textbbox((cx, y), ch, font=fonte, anchor="la")
                self.d.text((cx, y), ch, font=fonte, fill=cor, anchor="la")
                if ch.strip():
                    x0, y0 = min(x0 or b[0], b[0]), min(y0 or b[1], b[1])
                    x1, y1 = max(x1 or b[2], b[2]), max(y1 or b[3], b[3])
                cx += fonte.getlength(ch) + tracking * fonte.size
            caixa = (x0, y0, x1, y1)
        else:
            x += max(0, x - self.d.textbbox((x, y), s, font=fonte, anchor="la")[0])  # recuo lateral negativo
            self.d.text((x, y), s, font=fonte, fill=cor, anchor="la")
            caixa = self.d.textbbox((x, y), s, font=fonte, anchor="la")
        self.caixas.append({"tipo": tipo, "texto": s, "caixa": [round(v) for v in caixa]})
        return caixa


def largura_texto(s, fonte, tracking=0.0):
    return fonte.getlength(s) + tracking * fonte.size * max(0, len(s) - 1)


def quebrar(texto, fonte, largura, tracking=0.0):
    linhas = []
    for par in texto.split("\n"):
        atual = ""
        for w in par.split():
            teste = f"{atual} {w}".strip()
            if atual and largura_texto(teste, fonte, tracking) > largura:
                linhas.append(atual)
                atual = w
            else:
                atual = teste
        if atual:
            linhas.append(atual)
    return linhas


def ocupa(s, fonte):
    """Largura que a linha ocupa depois do deslocamento do recuo lateral negativo (Tela.linha)."""
    x0, _, x1, _ = fonte.getbbox(s, anchor="la")
    return x1 - min(0, x0)


def ajustar(texto, papel, peso, maximo, minimo, largura, linhas_max):
    """Maior corpo entre `maximo` e `minimo` em que o texto cabe na largura e no número de linhas."""
    t = maximo
    while True:
        f = M.fonte(papel, peso, t)
        ls = quebrar(texto, f, largura)
        if t <= minimo or (len(ls) <= linhas_max and all(ocupa(l, f) <= largura for l in ls)):
            return f, ls
        t = max(minimo, t - 4)


def altura(linhas, fonte, papel):
    asc, desc = fonte.getmetrics()
    return (len(linhas) - 1) * fonte.size * F["entrelinha"][papel] + asc + desc


def _texto(tela, x, y, linhas, fonte, cor, papel, tipo):
    for l in linhas:
        tela.linha(x, y, l, fonte, cor, tipo=tipo)
        y += fonte.size * F["entrelinha"][papel]
    return y


def conteudo(tela, x, y, largura, c, pal, cheio):
    """Eyebrow + hairline + destaque + texto + rodapé, empilhados a partir de (x, y). Devolve o y final."""
    sp = lambda k: M.px(f"spacing.{k}")
    if c.get("eyebrow"):
        f, tr = M.fonte("dado", 700, M.px("social.type.eyebrow")), F["tracking_eyebrow_em"]
        for l in quebrar(c["eyebrow"].upper(), f, largura, tr):
            tela.linha(x, y, l, f, pal["eyebrow"], tr, "eyebrow")
            y += f.size * F["entrelinha"]["dado"]
        y += M.px("component.eyebrow.gapBelow")
        tela.d.rectangle([x, y, x + largura, y + M.px("social.hairlineWidth") - 1], fill=pal["hairline"])
        y += M.px("social.hairlineWidth") + sp("lg")
    ordem = c.get("ordem") or (["destaque", "texto"] if NUMERO.match(c.get("destaque") or "") else ["texto", "destaque"])
    for parte in ordem:
        y = (_destaque if parte == "destaque" else _corpo)(tela, x, y, largura, c, pal, cheio)
    if c.get("rodape"):
        f = M.fonte("corpo", 400, M.px("social.type.source"))
        y = _texto(tela, x, y + sp("sm"), quebrar(c["rodape"], f, largura), f, pal["texto"], "corpo", "rodape")
    return y


def _destaque(tela, x, y, largura, c, pal, cheio):
    if c.get("destaque"):
        if NUMERO.match(c["destaque"]):
            f, ls = ajustar(c["destaque"], "dado", 700, M.px("social.type.statNumberMax"),
                            M.px("social.type.titleData"), largura, 1)
            y = _texto(tela, x, y, ls, f, pal["texto"], "dado", "destaque")
        else:
            maximo = M.px("social.type.titleMax") if cheio else M.px("social.type.titleData")
            minimo = M.px("social.type.titleCover") if cheio else M.px("social.type.body")
            f, ls = ajustar(c["destaque"], "titulo", 800, maximo, minimo, largura, 3)
            y = _texto(tela, x, y, ls, f, pal["texto"], "titulo", "destaque")
        y += M.px("spacing.lg")
    return y


def _corpo(tela, x, y, largura, c, pal, cheio):
    if c.get("texto"):
        f = M.fonte("titulo", 700, M.px("social.type.titleData")) if cheio else M.fonte("corpo", 400, M.px("social.type.body"))
        papel = "titulo" if cheio else "corpo"
        y = _texto(tela, x, y, quebrar(c["texto"], f, largura), f, pal["texto"], papel, "texto") + M.px("spacing.lg")
    return y


def assinatura(tela, y_topo, altura, escuro, pal):
    """Símbolo + handle numa linha (SOCIAL.md §3), centrados verticalmente na faixa [y_topo, y_topo+altura]."""
    x0 = M.zona_segura()[0]
    s = M.simbolo(escuro)
    tela.img.alpha_composite(s, (int(x0), int(y_topo + (altura - s.height) / 2)))
    f = M.fonte("dado", 400, M.px("social.type.handle"))
    y = y_topo + (altura - f.size) / 2
    tela.linha(x0 + s.width + M.px("spacing.sm"), y, F["handle"], f, pal["texto"], tipo="assinatura")
    tela.caixas.append({"tipo": "assinatura", "texto": "símbolo",
                        "caixa": [int(x0), int(y_topo + (altura - s.height) / 2), int(x0 + s.width),
                                  int(y_topo + (altura + s.height) / 2)]})


def cartao(c, destino, faixa_legenda):
    """PNG do cartão no quadro inteiro (transparente fora da caixa no modo sobreposto)."""
    W, H = dimensoes()
    x0, y0, x1, y1 = M.zona_segura()
    escuro = c.get("chassi", "C") == "B"
    pal = paleta(escuro)
    pad = M.px("spacing.xl")
    if c.get("modo") == "cheio":
        tela = Tela(W, H, pal["fundo"])
        conteudo(tela, x0, y0, x1 - x0, c, pal, cheio=True)
        # assinatura entre a faixa da legenda e o fim da zona segura (dentro da zona, fora da legenda)
        assinatura(tela, faixa_legenda[1] + M.px("spacing.sm"), y1 - faixa_legenda[1] - M.px("spacing.sm"), escuro, pal)
    else:
        camada = Tela(W, H)
        fim = conteudo(camada, x0 + pad, y0 + pad, x1 - x0 - 2 * pad, c, pal, cheio=False)
        tela = Tela(W, H)
        tela.d.rectangle([x0, y0, x1, fim + pad - M.px("spacing.sm")], fill=(*pal["fundo"], 255))
        tela.img.alpha_composite(camada.img)
        tela.caixas = camada.caixas
    tela.img.save(destino)
    return tela.caixas


def capa(c, destino):
    """Capa de Reels, chassi B (SOCIAL.md §3, §5.3, §6): eyebrow, hairline, mesh em campo, número e
    título ancorados embaixo, símbolo e handle em y 1568–1680 (banda dos tokens), sem ícone de play."""
    W, H = dimensoes()
    x0, y0, x1, y1 = M.zona_segura()
    pal = paleta(True)
    tela = Tela(W, H, pal["fundo"])
    largura = x1 - x0
    f_eb = M.fonte("dado", 700, M.px("social.type.eyebrow"))
    tela.linha(x0, y0, c["eyebrow"].upper(), f_eb, pal["eyebrow"], F["tracking_eyebrow_em"], "eyebrow")
    y_hair = y0 + f_eb.size * F["entrelinha"]["dado"] + M.px("component.eyebrow.gapBelow")
    tela.d.rectangle([x0, y_hair, x1, y_hair + M.px("social.hairlineWidth") - 1], fill=pal["hairline"])
    # título e número de baixo para cima, terminando no fim da zona segura
    f_t, ls_t = ajustar(c["texto"], "titulo", 800, F["capa_titulo"], M.px("social.type.titleCover"), largura, 2)
    f_n, ls_n = ajustar(c["destaque"], "dado", 700, F["capa_numero_max"], M.px("social.type.statNumberMax"), largura, 1)
    alt_t, alt_n = altura(ls_t, f_t, "titulo"), altura(ls_n, f_n, "dado")
    y_n = y1 - alt_t - M.px("spacing.md") - alt_n
    _texto(tela, x0, y_n, ls_n, f_n, pal["texto"], "dado", "destaque")
    _texto(tela, x0, y1 - alt_t, ls_t, f_t, pal["texto"], "titulo", "titulo")
    # mesh em campo entre a hairline e o número (nunca atrás de texto)
    cel = M.px("pattern.mesh.cellSize") * M.px("social.patternScale")
    traco = int(M.px("pattern.mesh.strokeWidth") * M.px("social.patternScale"))
    topo, base = y_hair + M.px("spacing.xl"), y_n - M.px("spacing.xl")
    if base - topo >= cel:
        mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(mesh)
        rgba = (*M.cor("pattern.mesh.color"), round(255 * F["opacidade_mesh"]))
        linhas_y = int((base - topo) // cel)
        colunas = int(largura // cel)
        for i in range(colunas + 1):
            d.rectangle([x0 + i * cel, topo, x0 + i * cel + traco - 1, topo + linhas_y * cel], fill=rgba)
        for j in range(linhas_y + 1):
            d.rectangle([x0, topo + j * cel, x0 + colunas * cel, topo + j * cel + traco - 1], fill=rgba)
        tela.img.alpha_composite(mesh)
    assinatura(tela, M.px("social.band.verticalTop"), M.px("social.band.height"), True, pal)
    tela.img.convert("RGB").save(destino)
    return tela.caixas
