"""Etapa 3: atribui cada arquivo a uma tomada, escolhe a melhor repetição e acha as âncoras por busca
aproximada nas palavras (difflib). O modelo (editor-video) só entra quando a âncora não aparece."""
import re
import unicodedata
from difflib import SequenceMatcher

from . import CFG


def norm(texto):
    """Palavras normalizadas: minúsculas, sem acento e sem pontuação ('12,40%' → '1240')."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return [w for w in (re.sub(r"\W", "", p) for p in t.split()) if w]


def palavras_norm(palavras):
    """Normaliza mantendo o índice da palavra original (uma palavra do Whisper pode virar zero ou mais)."""
    saida = []
    for i, p in enumerate(palavras):
        saida += [(w, i) for w in norm(p["w"])]
    return saida


def razao(a, b):
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def atribuir(storyboard, transcricao):
    """{tomada: {arquivo, razao, candidatos, justificativa}} e a lista de arquivos sem tomada."""
    falas = {t["id"]: norm(t["fala"]) for t in storyboard["tomadas"]}
    por_tomada, soltos = {}, []
    for arq, dados in transcricao["arquivos"].items():
        ws = [w for w, _ in palavras_norm(dados["palavras"])]
        notas = {tid: razao(ws, f) for tid, f in falas.items()}
        melhor = max(notas, key=notas.get)
        if notas[melhor] < CFG["alinhar"]["tomada_min"]:
            soltos.append({"arquivo": arq, "notas": {k: round(v, 3) for k, v in notas.items()}})
            continue
        por_tomada.setdefault(melhor, []).append((round(notas[melhor], 3), arq))
    escolha = {}
    for tid, cands in por_tomada.items():
        # maior semelhança com o roteiro; empate fica com a última gravada (nome em ordem)
        nota, arq = max(cands, key=lambda c: (c[0], c[1]))
        just = (f"única gravação ({nota:.0%} do roteiro)" if len(cands) == 1 else
                f"{arq}: {nota:.0%} do roteiro, contra " + ", ".join(f"{a} {n:.0%}" for n, a in cands if a != arq))
        escolha[tid] = {"arquivo": arq, "razao": nota, "candidatos": [a for _, a in cands], "justificativa": just}
    faltam = [t for t in falas if t not in escolha]
    return escolha, soltos, faltam


def ancorar(palavras, ancora):
    """(i, j, razão): índices da primeira e da última palavra do Whisper que melhor casam com a âncora."""
    ws = palavras_norm(palavras)
    alvo = norm(ancora)
    n = len(alvo)
    melhor = (0.0, 0, 0)
    for k in range(max(1, len(ws) - n + 1)):
        r = razao([w for w, _ in ws[k:k + n]], alvo)
        if r > melhor[0]:
            melhor = (r, k, k + n - 1)
    r, a, b = melhor
    if not ws:
        return None, None, 0.0
    return ws[a][1], ws[min(b, len(ws) - 1)][1], round(r, 3)
