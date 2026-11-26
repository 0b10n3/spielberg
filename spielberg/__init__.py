"""spielberg: storyboard.json + tomadas gravadas → MP4, capa e SRT do vídeo D+1."""
import json
import os
import subprocess
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent


def ler_yaml(p):
    p = Path(p)
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def gravar_yaml(p, dados):
    Path(p).write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def ler_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def gravar_json(p, dados):
    Path(p).write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


CFG = ler_yaml(RAIZ / "config/spielberg.yaml")
LOCAL = ler_yaml(RAIZ / "config/local.yaml") or ler_yaml(RAIZ / "config/local.exemplo.yaml")


def caminho(chave):
    """Caminho do local.yaml (midia, hemingway, marca), relativo à raiz do repo."""
    return (RAIZ / os.path.expanduser(LOCAL[chave])).resolve()


def projeto(slug):
    """Pasta versionada do vídeo (só texto)."""
    p = RAIZ / "projetos" / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def midia(slug, sub=""):
    """Pasta de mídia do vídeo, fora do git."""
    p = caminho("midia") / slug / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def rodar(args, **kw):
    """Roda ffmpeg/ffprobe com a lista de argumentos montada por código (nunca string de shell)."""
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError(f"{args[0]} falhou ({r.returncode}):\n{r.stderr[-3000:]}")
    return r


def ffprobe(arquivo):
    return json.loads(rodar(["ffprobe", "-v", "error", "-print_format", "json",
                             "-show_streams", "-show_format", arquivo]).stdout)
