"""Etapa 4: corta as pausas acima do limiar, só na fronteira de palavra e só em silêncio medido no áudio."""
import re

from . import CFG, rodar


def silencios(arquivo, db=None, minimo=None):
    c = CFG["corte"]
    r = rodar(["ffmpeg", "-hide_banner", "-nostats", "-i", arquivo, "-af",
               f"silencedetect=noise={db or c['silencio_db']}dB:d={minimo or c['silencio_min_s']}",
               "-f", "null", "-"])
    ini = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    fim = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(ini, fim + [float("inf")] * (len(ini) - len(fim))))


def trechos(palavras, sil, cauda_s=0.0):
    """Trechos mantidos [(ini, fim)] no relógio do arquivo.

    Uma pausa entre as palavras p e q só é cortada se o trecho comum entre a pausa do Whisper e um
    silêncio medido tiver pelo menos o limiar. O corte fica entre max(fim de p, início do silêncio)
    + margem e min(início de q, fim do silêncio) − margem: nunca dentro de uma palavra.
    """
    c = CFG["corte"]
    if not palavras:
        return []
    out, a = [], max(0.0, palavras[0]["ini"] - c["margem_antes_s"])
    for p, q in zip(palavras, palavras[1:]):
        for s0, s1 in sil:
            fala_fim, fala_ini = max(p["fim"], s0), min(q["ini"], s1)
            if fala_ini - fala_fim >= c["limiar_s"]:
                x, y = fala_fim + c["margem_depois_s"], fala_ini - c["margem_antes_s"]
                if y - x > 0.05:
                    out.append((round(a, 3), round(x, 3)))
                    a = y
                break
    out.append((round(a, 3), round(palavras[-1]["fim"] + c["margem_depois_s"] + cauda_s, 3)))
    return out
