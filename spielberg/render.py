"""Etapa 7: monta o filtergraph do ffmpeg por código a partir da timeline. Nenhum comando escrito à mão."""
import json
import re
import time

from . import CFG, ffprobe, rodar

# tags de cor nos próprios quadros: só as opções de saída não chegam ao VUI do x264 no ffmpeg 8
BT709 = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"


def _trechos(tl, fontes_dur, idx, so_audio=False):
    """Filtros de cada trecho K (trim + fades de áudio; congela o último quadro se passar do arquivo)."""
    fd = CFG["audio"]["fade_s"]
    partes, rotulos = [], []
    for n, k in enumerate(tl["K"]):
        i, dur_arq = idx[k["fonte"]], fontes_dur[k["fonte"]]
        fim = min(k["fim"], dur_arq)
        sobra = round(k["fim"] - fim, 3)
        d = round(fim - k["ini"], 3)
        if not so_audio:
            pad = f",tpad=stop_mode=clone:stop_duration={sobra}" if sobra > 0 else ""
            partes.append(f"[{i}:v]trim=start={k['ini']}:end={fim},setpts=PTS-STARTPTS{pad}[v{n}]")
        apad = f",apad=pad_dur={sobra}" if sobra > 0 else ""
        partes.append(f"[{i}:a]atrim=start={k['ini']}:end={fim},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:st=0:d={fd},afade=t=out:st={max(0, d - fd):.3f}:d={fd}{apad}[a{n}]")
        rotulos.append(f"[a{n}]" if so_audio else f"[v{n}][a{n}]")
    N = len(tl["K"])
    partes.append("".join(rotulos) + (f"concat=n={N}:v=0:a=1[ac]" if so_audio else f"concat=n={N}:v=1:a=1[vc][ac]"))
    return partes


def medir_loudness(tl, entradas, fontes_dur, idx):
    """1ª passada do loudnorm (só áudio): devolve os valores medidos."""
    a = CFG["audio"]
    g = ";".join(_trechos(tl, fontes_dur, idx, so_audio=True) +
                 [f"[ac]loudnorm=I={a['lufs']}:TP={a['pico_dbtp']}:LRA={a['lra']}:print_format=json[aout]"])
    r = rodar(["ffmpeg", "-hide_banner", "-nostats", *entradas, "-filter_complex", g, "-map", "[aout]", "-f", "null", "-"])
    return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)[0])


def montar(tl, mezanino, cartoes_concat, legendas_concat, destino, modo="previa"):
    """Gera o vídeo. Devolve (segundos de render, filtergraph)."""
    f, a = CFG["saida"]["final"], CFG["audio"]
    W, H = f["largura"], f["altura"]
    fontes_dur, idx, entradas = {}, {}, []
    for n, nome in enumerate(tl["fontes"]):
        arq = mezanino / nome
        fontes_dur[nome] = float(ffprobe(arq)["format"]["duration"])
        idx[nome] = n
        entradas += ["-i", arq]

    ic, il = len(entradas) // 2, len(entradas) // 2 + 1
    entradas += ["-f", "concat", "-safe", "0", "-i", cartoes_concat, "-f", "concat", "-safe", "0", "-i", legendas_concat]
    g = _trechos(tl, fontes_dur, idx)
    base = "vc"
    if tl["Z"]:
        g.append(f"[vc]split={len(tl['Z']) + 1}[z0]" + "".join(f"[zs{j}]" for j in range(1, len(tl["Z"]) + 1)))
        base = "z0"
        for j, z in enumerate(tl["Z"], 1):
            w2, h2 = round(W * z["para"] / 2) * 2, round(H * z["para"] / 2) * 2
            # o ponto do rosto (centro_y da altura) fica no mesmo lugar da tela depois do punch-in
            x, y = (w2 - W) // 2, min(h2 - H, max(0, round((h2 - H) * z["centro_y"])))
            g.append(f"[zs{j}]scale={w2}:{h2}:flags=lanczos,crop={W}:{H}:{x}:{y}[zz{j}]")
            g.append(f"[{base}][zz{j}]overlay=0:0:enable='between(t,{z['ini']},{z['fim']})'[zo{j}]")
            base = f"zo{j}"
    g.append(f"[{base}][{ic}:v]overlay=0:0:format=auto[vcart]")
    g.append(f"[vcart][{il}:v]overlay=0:0:format=auto[vleg]")
    escala = f",scale={CFG['saida']['previa']['largura']}:{CFG['saida']['previa']['altura']}:flags=bicubic" if modo == "previa" else ""
    g.append(f"[vleg]format=yuv420p{escala},setsar=1,{BT709}[vout]")
    if modo == "final":
        m = medir_loudness(tl, entradas[: 2 * len(tl["fontes"])], fontes_dur, idx)
        ln = (f"loudnorm=I={a['lufs']}:TP={a['pico_dbtp']}:LRA={a['lra']}:measured_I={m['input_i']}:"
              f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
              f"offset={m['target_offset']}:linear=true")
        cod = CFG["saida"]["final"]
    else:
        ln = f"loudnorm=I={a['lufs']}:TP={a['pico_dbtp']}:LRA={a['lra']}"
        cod = CFG["saida"]["previa"]
    g.append(f"[ac]{ln},aresample=48000[aout]")
    filtro = ";\n".join(g)
    t0 = time.time()
    rodar(["ffmpeg", "-y", "-hide_banner", "-v", "error", *entradas, "-filter_complex", filtro,
           "-map", "[vout]", "-map", "[aout]", "-t", tl["duracao"],
           "-c:v", "libx264", "-preset", cod["preset"], "-crf", cod["crf"], "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-r", f["fps"], "-fps_mode", "cfr",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-c:a", "aac", "-b:a", f"{f['audio_kbps']}k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", destino])
    return round(time.time() - t0, 1), filtro
