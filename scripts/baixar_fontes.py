"""Baixa as fontes da marca (google/fonts, licença OFL) para assets/fonts/ e confere as famílias.

Uso: uv run python scripts/baixar_fontes.py
As famílias são as do brand/DESIGN.md §4.2: Montserrat, Source Sans 3 e IBM Plex Mono.
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spielberg import marca  # noqa: E402

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl"
ARQUIVOS = {
    "montserrat": ["Montserrat%5Bwght%5D.ttf", "OFL.txt"],
    "sourcesans3": ["SourceSans3%5Bwght%5D.ttf", "OFL.txt"],
    "ibmplexmono": ["IBMPlexMono-Regular.ttf", "IBMPlexMono-Bold.ttf", "OFL.txt"],
}

marca.FONTES.mkdir(parents=True, exist_ok=True)
for pasta, nomes in ARQUIVOS.items():
    for nome in nomes:
        local = nome.replace("%5B", "[").replace("%5D", "]")
        destino = marca.FONTES / (f"OFL-{pasta}.txt" if nome == "OFL.txt" else local)
        if not destino.exists():
            urllib.request.urlretrieve(f"{BASE}/{pasta}/{nome}", destino)
        print(f"{destino.name}: {destino.stat().st_size // 1024} KB")

erros = marca.conferir_fontes()
print("\n".join(erros) if erros else "famílias conferidas: Montserrat, Source Sans 3, IBM Plex Mono")
sys.exit(1 if erros else 0)
