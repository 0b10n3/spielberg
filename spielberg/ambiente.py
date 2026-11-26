"""Etapa 0: confere ffmpeg, GPU, bibliotecas CUDA e fontes. Para com mensagem clara se faltar algo."""
import os
import sys
import sysconfig
from pathlib import Path

from . import rodar

FLAGS = ["libx264", "libzimg"]                      # x264 para codificar; zimg para o zscale do HDR
FILTROS = ["zscale", "tonemap", "loudnorm", "ebur128", "blackdetect", "freezedetect", "silencedetect",
           "overlay", "concat", "trim", "atrim", "tpad", "apad", "afade", "scale", "crop", "split"]


def libs_cuda():
    base = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
    return [str(base / p / "lib") for p in ("cublas", "cudnn") if (base / p / "lib").is_dir()]


def garantir_cuda():
    """O CTranslate2 acha cuBLAS/cuDNN pelo LD_LIBRARY_PATH, que precisa existir antes do processo
    (README do faster-whisper). Se faltar, reexecuta o próprio comando com a variável certa."""
    libs, atual = libs_cuda(), os.environ.get("LD_LIBRARY_PATH", "")
    if libs and not all(l in atual.split(":") for l in libs):
        os.environ["LD_LIBRARY_PATH"] = ":".join(libs + ([atual] if atual else []))
        os.execv(sys.executable, [sys.executable, "-m", "spielberg", *sys.argv[1:]])


def checar(whisper=False):
    from . import marca
    erros, info = [], {}
    info["ffmpeg"] = rodar(["ffmpeg", "-hide_banner", "-version"]).stdout.splitlines()[0]
    conf = rodar(["ffmpeg", "-hide_banner", "-buildconf"]).stdout
    erros += [f"ffmpeg sem --enable-{f}" for f in FLAGS if f"--enable-{f}" not in conf]
    nomes = {l.split()[1] for l in rodar(["ffmpeg", "-hide_banner", "-filters"]).stdout.splitlines()
             if l.startswith(" ") and len(l.split()) > 2}
    erros += [f"ffmpeg sem o filtro {f}" for f in FILTROS if f not in nomes]
    if "librsvg" not in rodar(["ffmpeg", "-hide_banner", "-decoders"]).stdout:
        erros.append("ffmpeg sem librsvg (símbolo da marca)")
    try:
        info["gpu"] = rodar(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used",
                             "--format=csv,noheader"]).stdout.strip()
    except (RuntimeError, FileNotFoundError):
        erros.append("nvidia-smi indisponível: a transcrição vai rodar na CPU, bem mais devagar")
    erros += marca.conferir_fontes()
    info["zona_segura"] = marca.zona_segura()
    info["tokens"] = marca.versao_tokens()
    try:
        import ctranslate2
        info["ctranslate2"] = f"{ctranslate2.__version__}, GPUs CUDA: {ctranslate2.get_cuda_device_count()}"
    except ImportError as e:
        erros.append(f"ctranslate2 ausente: {e}")
    if whisper:
        import numpy as np
        from faster_whisper import WhisperModel
        from . import CFG
        w = CFG["whisper"]
        m = WhisperModel(w["modelo"], device="cuda", compute_type=w["compute_type"])
        list(m.transcribe(np.zeros(16000, dtype=np.float32), language=w["idioma"])[0])
        info["whisper"] = f"{w['modelo']} ({w['compute_type']}) carregou e transcreveu na GPU"
    return erros, info
