"""Mídia sintética para os testes: vídeo do lavfi e 'fala' = tom de 440 Hz nos intervalos dados."""
import spielberg
from spielberg import rodar


def tomada(destino, falas, dur, extra=()):
    """Arquivo 1080×1920 30 fps com áudio: tom onde há 'fala' [(ini, fim)], silêncio no resto."""
    expr = "+".join(f"between(t,{a},{b})" for a, b, *_ in falas)
    rodar(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=1080x1920:r=30:d={dur}",
           "-f", "lavfi", "-i", f"aevalsrc='0.3*sin(2*PI*440*t)*({expr})':s=48000:d={dur}",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "pcm_s16le", *extra, destino])
    return destino


def palavras(trechos_texto):
    """[(ini, fim, 'texto da frase')] → palavras com tempos divididos por igual dentro de cada trecho."""
    out = []
    for a, b, texto in trechos_texto:
        ws = texto.split()
        passo = (b - a) / len(ws)
        out += [{"w": w, "ini": round(a + i * passo, 3), "fim": round(a + (i + 1) * passo, 3), "p": 0.99}
                for i, w in enumerate(ws)]
    return out


def usar_midia(tmp):
    spielberg.LOCAL["midia"] = str(tmp)
