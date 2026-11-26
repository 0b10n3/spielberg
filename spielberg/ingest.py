"""Etapa 1: sonda cada tomada e gera o mezanino (1080×1920, 30 fps constantes, SDR BT.709, áudio 48 kHz)."""
import hashlib
import shutil

from . import CFG, caminho, ffprobe, gravar_json, midia, projeto, rodar
from .render import BT709

EXTENSOES = {".mp4", ".mov", ".m4v", ".mkv"}
HDR = {"arib-std-b67", "smpte2084"}  # HLG (iPhone) e PQ


def _fracao(s):
    n, d = (int(x) for x in s.split("/"))
    return n / d if d else 0.0


def sondar(arquivo):
    d = ffprobe(arquivo)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    rot = int(v.get("tags", {}).get("rotate", 0))
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", rot))
    w, h = (v["height"], v["width"]) if rot % 180 else (v["width"], v["height"])
    return {"arquivo": arquivo.name, "largura": w, "altura": h, "rotacao": rot,
            "fps": round(_fracao(v["avg_frame_rate"]), 3), "vfr": v["r_frame_rate"] != v["avg_frame_rate"],
            "transfer": v.get("color_transfer"), "hdr": v.get("color_transfer") in HDR,
            "audio": any(s["codec_type"] == "audio" for s in d["streams"]),
            "duracao": round(float(d["format"]["duration"]), 3)}


def filtro_video(info):
    f = CFG["saida"]["final"]
    W, H = f["largura"], f["altura"]
    tonemap = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
               "zscale=t=bt709:m=bt709:r=tv," if info["hdr"] else "")
    return (f"{tonemap}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
            f"fps={f['fps']},format=yuv420p,{BT709}")


def copiar_storyboard(slug):
    """Cópia do contrato do hemingway com o sha256 da origem (o spielberg só lê o hemingway)."""
    origem = caminho("hemingway") / "posts" / slug / "distribuicao/video/storyboard.json"
    destino = projeto(slug) / "storyboard.json"
    shutil.copyfile(origem, destino)
    return hashlib.sha256(origem.read_bytes()).hexdigest()


def ingerir(slug):
    brutos, mezanino = midia(slug, "brutos"), midia(slug, "mezanino")
    tomadas, avisos = [], []
    for arq in sorted(p for p in brutos.iterdir() if p.suffix.lower() in EXTENSOES):
        info = sondar(arq)
        destino = mezanino / f"{arq.stem}.mkv"
        if not destino.exists() or destino.stat().st_mtime < arq.stat().st_mtime:
            rodar(["ffmpeg", "-y", "-v", "error", "-i", arq, "-vf", filtro_video(info),
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-g", "15",
                   "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                   "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", destino])
        info["mezanino"] = destino.name
        if info["hdr"]:
            avisos.append(f"{arq.name}: gravado em HDR ({info['transfer']}); convertido para SDR. "
                          "Regravar com o HDR desligado dá cor melhor.")
        if not info["audio"]:
            avisos.append(f"{arq.name}: sem áudio")
        if (info["largura"], info["altura"]) != (1080, 1920):
            avisos.append(f"{arq.name}: {info['largura']}×{info['altura']} (esperado 1080×1920); reenquadrado")
        tomadas.append(info)
    if not tomadas:
        raise SystemExit(f"nenhuma tomada em {brutos}")
    sha = copiar_storyboard(slug)
    gravar_json(projeto(slug) / "ingest.json", {"storyboard_sha256": sha, "tomadas": tomadas, "avisos": avisos})
    return tomadas, avisos
