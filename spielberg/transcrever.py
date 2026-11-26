"""Etapa 2: faster-whisper local, com tempo por palavra e VAD; transcricao.md para o 🛑 do autor."""
import re
from difflib import SequenceMatcher

from . import CFG, gravar_json, ler_json, midia, projeto
from .alinhar import atribuir, norm

NUMERO = re.compile(r"R\$\s?\d[\d.]*(?:,\d+)?|\d[\d.]*(?:,\d+)?\s?%|\b\d[\d.]*(?:,\d+)?\b")


def glossario(storyboard):
    """Termos e números que o autor vai falar, tirados das falas do roteiro (ajuda a grafia do Whisper)."""
    falas = " ".join(t["fala"] for t in storyboard["tomadas"])
    termos = re.findall(r"\b(?:Tesouro [A-ZÁ-Ú]\w+(?: \d{4})?|[A-Z]{2,}\w*|[A-ZÁ-Ú][a-zá-ú]+(?= [A-ZÁ-Ú]))", falas)
    termos += re.findall(r"\b(?:Selic|Copom|Focus|Syntaxis)\b", falas)
    return ", ".join(dict.fromkeys(t.strip() for t in termos + NUMERO.findall(falas)))


def transcrever(slug, so=None, modelo=None, compute_type=None, jargao=None):
    from faster_whisper import WhisperModel
    w = CFG["whisper"]
    modelo, compute_type, jargao = modelo or w["modelo"], compute_type or w["compute_type"], jargao or w["jargao"]
    m = WhisperModel(modelo, device="cuda", compute_type=compute_type)
    sb = ler_json(projeto(slug) / "storyboard.json")
    g = glossario(sb)
    caminho = projeto(slug) / "transcricao.json"
    res = ler_json(caminho) if caminho.exists() and so else {"arquivos": {}}
    res.update(modelo=modelo, compute_type=compute_type, jargao=jargao, glossario=g, aprovada=False)
    for info in ler_json(projeto(slug) / "ingest.json")["tomadas"]:
        if so and info["mezanino"] != so:
            continue
        segs, _ = m.transcribe(str(midia(slug, "mezanino") / info["mezanino"]), language=w["idioma"],
                               beam_size=w["beam_size"], word_timestamps=True, vad_filter=w["vad_filter"],
                               **({"initial_prompt": g} if jargao == "initial_prompt" else {"hotwords": g}))
        res["arquivos"][info["mezanino"]] = {
            "duracao": info["duracao"],
            "palavras": [{"w": x.word.strip(), "ini": round(x.start, 3), "fim": round(x.end, 3),
                          "p": round(x.probability, 3)} for s in segs for x in s.words]}
    gravar_json(caminho, res)
    relatorio(slug)
    return res


def texto(palavras):
    return " ".join(p["w"] for p in palavras)


def relatorio(slug):
    """transcricao.md: fala gravada ao lado do roteiro, com números e termos em destaque."""
    sb = ler_json(projeto(slug) / "storyboard.json")
    tr = ler_json(projeto(slug) / "transcricao.json")
    escolha, soltos, faltam = atribuir(sb, tr)
    linhas = [f"# Transcrição · {slug}", "",
              f"Modelo `{tr['modelo']}` ({tr['compute_type']}), jargão por `{tr['jargao']}`. "
              f"Situação: **{'aprovada' if tr.get('aprovada') else 'aguardando conferência'}**.", "",
              "Confira os **números** e os termos. Correção: `/spielberg corrigir <slug> <arquivo> \"de\" \"para\"` "
              "(mantém os tempos das palavras).", ""]
    for t in sb["tomadas"]:
        e = escolha.get(t["id"])
        linhas += [f"## {t['id']} · {t['bloco']}", ""]
        if not e:
            linhas += ["**Nenhum arquivo casou com esta tomada.**", ""]
            continue
        gravado = texto(tr["arquivos"][e["arquivo"]]["palavras"])
        linhas += [f"Arquivo `{e['arquivo']}` · {e['justificativa']}", "",
                   "| Roteiro | Gravado |", "|---|---|",
                   f"| {t['fala'].replace(chr(10), ' ')} | {NUMERO.sub(lambda m: f'**{m[0]}**', gravado)} |", ""]
        a, b = norm(t["fala"]), norm(gravado)
        difs = [f"- roteiro “{' '.join(a[i1:i2]) or '∅'}” → gravado “{' '.join(b[j1:j2]) or '∅'}”"
                for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op != "equal"]
        linhas += (["Diferenças:"] + difs if difs else ["Igual ao roteiro."]) + [""]
        baixa = [p for p in tr["arquivos"][e["arquivo"]]["palavras"] if p["p"] < 0.5]
        if baixa:
            linhas += ["Palavras com baixa confiança: " + ", ".join(f"“{p['w']}” ({p['ini']:.1f} s)" for p in baixa), ""]
    if soltos:
        linhas += ["## Arquivos sem tomada", ""] + [f"- `{s['arquivo']}`: {s['notas']}" for s in soltos] + [""]
    if faltam:
        linhas += [f"**Tomadas sem gravação:** {', '.join(faltam)}", ""]
    (projeto(slug) / "transcricao.md").write_text("\n".join(linhas), encoding="utf-8")
    return escolha, soltos, faltam


def corrigir(slug, arquivo, de, para):
    """Troca o texto de uma sequência de palavras sem perder os tempos (redistribui se mudar a contagem)."""
    caminho = projeto(slug) / "transcricao.json"
    tr = ler_json(caminho)
    pal = tr["arquivos"][arquivo]["palavras"]
    alvo, novo = de.split(), para.split()
    for i in range(len(pal) - len(alvo) + 1):
        if [norm(p["w"]) for p in pal[i:i + len(alvo)]] == [norm(w) for w in alvo]:
            ini, fim = pal[i]["ini"], pal[i + len(alvo) - 1]["fim"]
            passo = (fim - ini) / len(novo)
            pal[i:i + len(alvo)] = [{"w": w, "ini": round(ini + k * passo, 3), "fim": round(ini + (k + 1) * passo, 3),
                                     "p": 1.0, "corrigida": True} for k, w in enumerate(novo)]
            tr["aprovada"] = False
            gravar_json(caminho, tr)
            relatorio(slug)
            return True
    return False
