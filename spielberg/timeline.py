"""Timeline como código: storyboard + transcrição aprovada → trechos (K), cartões (C), zooms (Z) e
legendas (L), com os tempos das sobreposições no relógio do vídeo final. Ajustes do autor são deltas
por ID em ajustes.yaml, aplicados sobre a geração; por isso sobrevivem a uma nova geração."""
import re

from . import CFG, midia
from .alinhar import ancorar
from .cortar import silencios, trechos

DELTAS = {"deslocar_inicio_s": ("ini",), "deslocar_fim_s": ("fim",), "deslocar_s": ("ini", "fim")}
FIM_DE_FRASE = re.compile(r"[.?!:;]$")


def aplicar(itens, ajustes):
    """Aplica os ajustes cujo ID existe em `itens`. Devolve a lista sem os removidos."""
    saida = []
    for it in itens:
        a = ajustes.get(it["id"]) or {}
        if a.get("remover"):
            continue
        for chave, v in a.items():
            if chave in DELTAS:
                for campo in DELTAS[chave]:
                    it[campo] = round(it[campo] + v, 3)
            elif chave != "remover":
                it[chave] = v
        saida.append(it)
    return saida


def _relogio(K):
    """Função (tomada, t local) → t no vídeo final. Tempo dentro de um corte cola no trecho seguinte."""
    def saida(tomada, t):
        acc = 0.0
        for k in K:
            if k["tomada"] == tomada and t <= k["fim"]:
                return round(acc + max(0.0, t - k["ini"]), 3)
            acc += k["fim"] - k["ini"]
        return round(acc, 3)
    return saida


def legendas(K, transcricao, n_max):
    blocos, atual, t0 = [], [], 0.0
    def fechar():
        if atual:
            blocos.append({"ini": atual[0][0], "fim": atual[-1][1], "texto": " ".join(w for _, _, w in atual)})
            atual.clear()
    for k in K:
        for p in transcricao["arquivos"][k["fonte"]]["palavras"]:
            if p["ini"] >= k["ini"] - 0.01 and p["fim"] <= k["fim"] + 0.01:
                ini, fim = t0 + p["ini"] - k["ini"], t0 + p["fim"] - k["ini"]
                if atual and ini - atual[-1][1] > 0.6:
                    fechar()
                atual.append((round(ini, 3), round(fim, 3), p["w"]))
                if len(atual) >= n_max or FIM_DE_FRASE.search(p["w"]):
                    fechar()
        fechar()  # bloco nunca atravessa um corte
        t0 += k["fim"] - k["ini"]
    emendar = CFG["legenda"]["emendar_s"]
    for b, prox in zip(blocos, blocos[1:]):
        if prox["ini"] - b["fim"] < emendar:
            b["fim"] = prox["ini"]
    return [{"id": f"L{i}", **b} for i, b in enumerate(blocos, 1)]


def gerar(slug, storyboard, transcricao, escolha, ajustes=None, sil=None):
    """Timeline completa. `sil` (silêncios por arquivo) pode vir de fora nos testes."""
    ajustes = dict(ajustes or {})
    avisos, ancoras, K = [], {}, []
    for t in storyboard["tomadas"]:
        arq = escolha[t["id"]]["arquivo"]
        pal = transcricao["arquivos"][arq]["palavras"]
        cenas = [c for c in storyboard["cenas"] if c["tomada"] == t["id"]]
        for c in cenas:
            i, _, r1 = ancorar(pal, c["ancora_inicio"])
            _, j, r2 = ancorar(pal, c["ancora_fim"])
            if min(r1, r2) < CFG["alinhar"]["similaridade_min"]:
                avisos.append(f"{c['id']}: âncora difusa ({r1:.0%} / {r2:.0%}); peça ao editor-video para ancorar")
            ancoras[c["id"]] = (t["id"], pal[i]["ini"], pal[j]["fim"])
        t_ini = min(ancoras[c["id"]][1] for c in cenas)
        t_fim = max(ancoras[c["id"]][2] for c in cenas)
        falado = [p for p in pal if p["ini"] >= t_ini - 0.01 and p["fim"] <= t_fim + 0.01]
        cauda = max([c["cartao"].get("segurar_s", 0) for c in cenas if c.get("cartao")] + [0])
        s = sil[arq] if sil else silencios(midia(slug, "mezanino") / arq)
        for a, b in trechos(falado, s, cauda_s=cauda):
            K.append({"id": f"K{len(K) + 1}", "tomada": t["id"], "fonte": arq, "ini": a, "fim": b})
    ids_K = {k["id"] for k in K}
    K = aplicar(K, {k: v for k, v in ajustes.items() if k in ids_K})
    saida = _relogio(K)
    duracao = round(sum(k["fim"] - k["ini"] for k in K), 3)

    C, Z, S = [], [], []
    for c in storyboard["cenas"]:
        tom, a, b = ancoras[c["id"]]
        ini, fim = saida(tom, a), saida(tom, b)
        S.append({"id": c["id"], "ini": ini, "fim": fim})
        if (cartao := c.get("cartao")):
            if cartao.get("segurar_s"):
                ini, fim = fim, min(duracao, fim + cartao["segurar_s"])
            C.append({"id": cartao["id"], "cena": c["id"], "ini": 0.0 if not C and ini < 0.5 else ini,
                      "fim": fim, **{k: v for k, v in cartao.items() if k not in ("id",)}})
        if (z := c.get("zoom")):
            Z.append({"id": f"Z{len(Z) + 1}", "cena": c["id"], "ini": ini, "fim": fim,
                      "para": z["para"], "centro_y": CFG["zoom"]["centro_y"]})
    n = min(CFG["legenda"]["palavras_por_bloco"], storyboard.get("legenda", {}).get("palavras_por_bloco_max", 99))
    L = legendas(K, transcricao, n)
    conhecidos = ids_K | {x["id"] for x in C + Z + L}
    avisos += [f"ajuste {k}: ID não existe mais na timeline; não aplicado" for k in ajustes if k not in conhecidos]
    resto = {k: v for k, v in ajustes.items() if k not in ids_K}
    C, Z, L = aplicar(C, resto), aplicar(Z, resto), aplicar(L, resto)
    for x, y in zip(C, C[1:]):
        if y["ini"] < x["fim"]:
            x["fim"] = y["ini"]  # um cartão por vez: o seguinte corta o anterior
    return {"versao": 1, "slug": slug, "duracao": duracao, "fontes": sorted({k["fonte"] for k in K}),
            "S": S, "K": K, "C": C, "Z": Z, "L": L, "avisos": avisos}
