"""Etapa 8: checagens em código (qualquer falha reprova o render) e a folha de quadros com as guias."""
import re
import struct
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from . import CFG, ffprobe, rodar
from . import marca as M

NUM = re.compile(r"(R\$\s?)?(\d[\d.]*(?:,\d+)?)(\s?(?:mil\b|%))?", re.I)
DATA = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
ANO = re.compile(r"^(19|20)\d{2}$")


def numeros(texto):
    """Números canônicos de um texto ('R$ 13.405' → '13405'; '12,40%' → '12.4%'; '10 mil' → '10000').
    Datas e anos soltos não contam como número."""
    out = set()
    for m in NUM.finditer(DATA.sub(" ", texto)):
        bruto, sufixo = m[2].rstrip("."), (m[3] or "").strip().lower()
        if ANO.match(bruto) and not m[1] and not sufixo:
            continue
        v = float(bruto.replace(".", "").replace(",", "."))
        v = v * 1000 if sufixo == "mil" else v
        out.add(f"{v:g}" + ("%" if sufixo == "%" else ""))
    return out


def checar_numeros(textos_tela, post, transcricao):
    no_post, falados = numeros(post), numeros(transcricao)
    falhas = []
    for onde, texto in textos_tela:
        for n in sorted(numeros(texto)):
            if n not in no_post:
                falhas.append(f"{onde}: número {n} não está no post")
            if n not in falados:
                falhas.append(f"{onde}: número {n} não foi falado (transcrição aprovada)")
    return falhas


def checar_caixas(itens, zona, faixa):
    """itens: [(id, tipo_item, caixas)], tipo_item ∈ {cartao, legenda, capa}."""
    x0, y0, x1, y1 = zona
    falhas = []
    for ident, tipo_item, caixas in itens:
        for c in caixas:
            bx0, by0, bx1, by1 = c["caixa"]
            if tipo_item == "capa" and c["tipo"] == "assinatura":
                continue  # SOCIAL.md §3: na capa de Reels, símbolo e handle ficam em y 1568–1680
            if not (x0 <= bx0 and bx1 <= x1 and y0 <= by0 and by1 <= y1):
                falhas.append(f"{ident}: “{c['texto'][:30]}” {c['caixa']} fora da zona segura {list(zona)}")
            if tipo_item == "cartao" and c["tipo"] != "assinatura" and by1 > faixa[0] and by0 < faixa[1]:
                falhas.append(f"{ident}: “{c['texto'][:30]}” invade a faixa da legenda {list(faixa)}")
            if tipo_item == "legenda" and not (faixa[0] <= by0 and by1 <= faixa[1]):
                falhas.append(f"{ident}: legenda {c['caixa']} fora da faixa {list(faixa)}")
    return falhas


def moov_antes_do_mdat(arquivo):
    with open(arquivo, "rb") as f:
        pos = 0
        while (cab := f.read(8)) and len(cab) == 8:
            tam, tipo = struct.unpack(">I4s", cab)
            if tam == 1:
                tam = struct.unpack(">Q", f.read(8))[0]
            if tipo in (b"moov", b"mdat"):
                return tipo == b"moov"
            pos += tam
            f.seek(pos)
    return False


def especificacoes(arquivo, modo, faixa_duracao):
    d = ffprobe(arquivo)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), {})
    alvo = CFG["saida"]["final" if modo == "final" else "previa"]
    dur = float(d["format"]["duration"])
    checks = [
        ("resolução", (v["width"], v["height"]) == (alvo["largura"], alvo["altura"]), f"{v['width']}×{v['height']}"),
        ("30 fps constantes", v["r_frame_rate"] == v["avg_frame_rate"] == "30/1", f"{v['r_frame_rate']} / {v['avg_frame_rate']}"),
        ("H.264 High", v["codec_name"] == "h264" and v.get("profile") == "High", f"{v['codec_name']} {v.get('profile')}"),
        ("yuv420p", v.get("pix_fmt") == "yuv420p", v.get("pix_fmt")),
        ("BT.709", v.get("color_space") == v.get("color_primaries") == v.get("color_transfer") == "bt709",
         f"{v.get('color_space')}/{v.get('color_primaries')}/{v.get('color_transfer')}"),
        ("AAC 48 kHz estéreo", a.get("codec_name") == "aac" and a.get("sample_rate") == "48000" and a.get("channels") == 2,
         f"{a.get('codec_name')} {a.get('sample_rate')} {a.get('channels')} canais"),
        ("faststart", moov_antes_do_mdat(arquivo), "moov antes do mdat"),
        ("duração na faixa do storyboard", faixa_duracao[0] <= dur <= faixa_duracao[1], f"{dur:.1f} s em {faixa_duracao}"),
    ]
    return checks, dur


def loudness(arquivo):
    r = rodar(["ffmpeg", "-hide_banner", "-nostats", "-i", arquivo, "-af", "ebur128=peak=true", "-f", "null", "-"])
    resumo = r.stderr[r.stderr.rfind("Summary:"):]
    pega = lambda rx: float(re.search(rx, resumo, re.S)[1])
    return {"I": pega(r"I:\s+(-?[\d.]+) LUFS"), "LRA": pega(r"LRA:\s+([\d.]+) LU"),
            "pico": pega(r"True peak:.*?Peak:\s+(-?[\d.]+) dBFS")}


def detectores(arquivo, sem_congelado=(), sem_silencio=()):
    q = CFG["qa"]
    r = rodar(["ffmpeg", "-hide_banner", "-nostats", "-i", arquivo,
               "-vf", f"blackdetect=d={q['preto_s']}:pix_th=0.10,freezedetect=n=-60dB:d={q['congelado_s']}",
               "-af", f"silencedetect=noise={q['silencio_db']}dB:d={q['silencio_max_s']}", "-f", "null", "-"])
    e = r.stderr
    pares = lambda a, b: list(zip(map(float, re.findall(a, e)), map(float, re.findall(b, e) + ["1e9"] * 99)))
    fora = lambda ivs, exc: [(a, b) for a, b in ivs if not any(a < y and b > x for x, y in exc)]
    return {"preto": pares(r"black_start:([\d.]+)", r"black_end:([\d.]+)"),
            "congelado": fora(pares(r"freeze_start: ([\d.]+)", r"freeze_end: ([\d.]+)"), sem_congelado),
            "silencio": fora(pares(r"silence_start: (-?[\d.]+)", r"silence_end: ([\d.]+)"), sem_silencio)}


def folha_de_quadros(arquivo, cenas, destino, capa=None, faixa=None):
    """Um quadro por cena, com a zona segura e a faixa da legenda desenhadas (só nesta cópia de QA)."""
    tw, th = 360, 640
    k = tw / M.px("social.format.vertical.width")
    zona = [v * k for v in M.zona_segura()]
    quadros = []
    with tempfile.TemporaryDirectory() as tmp:
        for c in cenas:
            t = (c["ini"] + c["fim"]) / 2
            png = Path(tmp) / f"{c['id']}.png"
            rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", arquivo, "-frames:v", "1",
                   "-vf", f"scale={tw}:{th}", png])
            quadros.append((f"{c['id']} · {t:.1f} s", Image.open(png).convert("RGB")))
        if capa:
            quadros.append(("capa", Image.open(capa).convert("RGB").resize((tw, th))))
    cols = 3
    folha = Image.new("RGB", (cols * (tw + 16) + 16, ((len(quadros) + cols - 1) // cols) * (th + 48) + 16), (40, 40, 40))
    d = ImageDraw.Draw(folha)
    for n, (rotulo, img) in enumerate(quadros):
        x, y = 16 + (n % cols) * (tw + 16), 16 + (n // cols) * (th + 48)
        folha.paste(img, (x, y))
        d.rectangle([x + zona[0], y + zona[1], x + zona[2], y + zona[3]], outline=(255, 64, 64), width=2)
        if faixa:
            for fy in faixa:
                d.line([x, y + fy * k, x + tw, y + fy * k], fill=(64, 160, 255), width=1)
        d.text((x, y + th + 8), rotulo, fill=(240, 240, 240))
    folha.save(destino)
    return destino
