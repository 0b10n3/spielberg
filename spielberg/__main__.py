"""CLI do spielberg: uv run python -m spielberg <comando> <slug> [opções].

ambiente · ingest · transcrever · corrigir · aprovar-transcricao · alinhar · previa · aprovar-corte · final
"""
import argparse
import hashlib
import shutil
import sys
from datetime import datetime

from . import CFG, caminho, gravar_json, gravar_yaml, ler_json, ler_yaml, midia, projeto

ORDEM = ["transcrito", "transcricao-aprovada", "previa", "corte-aprovado", "entregue"]


def estado(slug, **mudar):
    p = projeto(slug) / "render.json"
    r = ler_json(p) if p.exists() else {"versao_esquema": "1.0", "situacao": None, "versao": 0}
    if mudar:
        r.update(mudar, gerado_em=datetime.now().astimezone().isoformat(timespec="seconds"))
        gravar_json(p, r)
    return r


def exigir(slug, situacao):
    atual = estado(slug).get("situacao")
    if atual not in ORDEM or ORDEM.index(atual) < ORDEM.index(situacao):
        sys.exit(f"etapa bloqueada: precisa de '{situacao}', situação atual '{atual}'")


def preparar(slug):
    """Timeline gerada (pura, gravada) e a timeline com os ajustes do autor (usada no render)."""
    from .alinhar import atribuir
    from .cortar import silencios
    from .timeline import gerar
    sb = ler_json(projeto(slug) / "storyboard.json")
    tr = ler_json(projeto(slug) / "transcricao.json")
    escolha, soltos, faltam = atribuir(sb, tr)
    if faltam:
        sys.exit(f"tomadas sem gravação: {faltam} (veja transcricao.md)")
    sil = {e["arquivo"]: silencios(midia(slug, "mezanino") / e["arquivo"]) for e in escolha.values()}
    gerada = gerar(slug, sb, tr, escolha, sil=sil)
    gravar_yaml(projeto(slug) / "timeline.gerada.yaml", gerada)
    ajustes = ler_yaml(projeto(slug) / "ajustes.yaml") or {}
    tl = gerar(slug, sb, tr, escolha, ajustes, sil=sil) if ajustes else gerada
    return sb, tr, escolha, tl


def renderizar(slug, modo):
    from . import cartoes, legendas, qa, render
    from .marca import versao_tokens, zona_segura
    sb, tr, escolha, tl = preparar(slug)
    pasta = midia(slug, "cartoes")
    faixa = legendas.faixa()
    itens = []
    for c in tl["C"]:
        c["png"] = f"{c['id']}.png"
        itens.append((c["id"], "cartao", cartoes.cartao(c, pasta / c["png"], faixa)))
    for b in tl["L"]:
        b["png"] = f"{b['id']}.png"
        itens.append((b["id"], "legenda", legendas.bloco(b["texto"], pasta / b["png"])))
    capa = pasta / "capa.png"
    itens.append(("capa", "capa", cartoes.capa(sb["capa"], capa)))
    cc = legendas.concat(tl["C"], tl["duracao"], pasta, "cartoes")
    lc = legendas.concat(tl["L"], tl["duracao"], pasta, "legendas")
    r = estado(slug)
    versao = r.get("versao", 0) + (1 if modo == "previa" else 0)
    destino = (midia(slug, "previas") / f"v{versao:02d}.mp4" if modo == "previa"
               else midia(slug, "saida") / f"{slug}-d1.mp4")
    segundos, filtro = render.montar(tl, midia(slug, "mezanino"), cc, lc, destino, modo)
    (midia(slug, "qa") / f"filtro-{modo}.txt").write_text(filtro, encoding="utf-8")

    falhas, avisos = [], list(tl["avisos"])
    checks, dur = qa.especificacoes(destino, modo, sb["formato"]["duracao_alvo_s"])
    falhas += [f"{n}: {v}" for n, ok, v in checks if not ok]
    falhas += qa.checar_caixas(itens, zona_segura(), faixa)
    tela = [(c["id"], " ".join(str(c.get(k) or "") for k in ("eyebrow", "texto", "destaque", "rodape"))) for c in tl["C"]]
    tela.append(("capa", " ".join(str(sb["capa"].get(k) or "") for k in ("eyebrow", "texto", "destaque"))))
    post = (caminho("hemingway") / "posts" / slug / "post.md").read_text(encoding="utf-8")
    falado = " ".join(p["w"] for e in escolha.values() for p in tr["arquivos"][e["arquivo"]]["palavras"])
    falhas += qa.checar_numeros(tela, post, falado)
    loud, a = qa.loudness(destino), CFG["audio"]
    fora = abs(loud["I"] - a["lufs"]) > a["tolerancia_lu"] or loud["pico"] > a["pico_dbtp"]
    msg = f"loudness {loud['I']} LUFS, pico {loud['pico']} dBTP (alvo {a['lufs']} ± {a['tolerancia_lu']}, ≤ {a['pico_dbtp']})"
    if fora:
        (falhas if modo == "final" else avisos).append(msg)
    cheios = [(c["ini"], c["fim"]) for c in tl["C"] if c.get("modo") == "cheio"]
    finais = [(c["ini"], c["fim"]) for c in tl["C"] if c.get("segurar_s")]
    det = qa.detectores(destino, cheios, finais)
    falhas += [f"{tipo} em {x:.1f}–{y:.1f} s" for tipo, ivs in det.items() for x, y in ivs]
    folha = qa.folha_de_quadros(destino, tl["S"], midia(slug, "qa") / f"contact_sheet-{modo}.png", capa, faixa)

    linhas = [f"## {'Prévia v%02d' % versao if modo == 'previa' else 'Final'} · "
              f"{datetime.now():%Y-%m-%d %H:%M} · render {segundos} s · {dur:.1f} s de vídeo", "",
              "| Checagem | Resultado | Valor |", "|---|---|---|"]
    linhas += [f"| {n} | {'ok' if ok else '**falha**'} | {v} |" for n, ok, v in checks]
    linhas += [f"| loudness | {'ok' if not fora else 'fora'} | {loud['I']} LUFS · pico {loud['pico']} · LRA {loud['LRA']} |",
               f"| caixas na zona segura | {'ok' if not [f for f in falhas if 'zona' in f or 'faixa' in f] else '**falha**'} | "
               f"{sum(len(c) for _, _, c in itens)} caixas medidas |",
               f"| números da tela | {'ok' if not [f for f in falhas if 'número' in f] else '**falha**'} | post + transcrição |",
               f"| preto · congelado · silêncio | {'ok' if not any(det.values()) else '**falha**'} | "
               f"{len(det['preto'])} · {len(det['congelado'])} · {len(det['silencio'])} |", ""]
    linhas += (["Falhas:"] + [f"- {f}" for f in falhas] + [""]) if falhas else []
    linhas += (["Avisos:"] + [f"- {x}" for x in avisos] + [""]) if avisos else []
    qa_md = projeto(slug) / "qa.md"
    anterior = qa_md.read_text(encoding="utf-8") if qa_md.exists() else f"# QA · {slug}\n\n"
    qa_md.write_text(anterior + "\n".join(linhas) + "\n", encoding="utf-8")

    extra = {}
    if modo == "final" and not falhas:
        saida = midia(slug, "saida")
        legendas.srt(tl["L"], saida / f"{slug}-d1.srt")
        shutil.copyfile(capa, saida / f"{slug}-capa.png")
        extra = {"situacao": "entregue", "caminho_saida": str(destino), "duracao_s": round(dur, 2),
                 "sha256": hashlib.sha256(destino.read_bytes()).hexdigest(), "versao_tokens_marca": versao_tokens()}
    elif modo == "previa":
        extra = {"situacao": "previa", "versao": versao, "duracao_s": round(dur, 2)}
    if extra:
        estado(slug, **extra)
    return destino, folha, falhas, avisos, segundos


def main():
    ap = argparse.ArgumentParser(prog="spielberg")
    ap.add_argument("comando", choices=["ambiente", "ingest", "transcrever", "corrigir", "aprovar-transcricao",
                                        "alinhar", "previa", "aprovar-corte", "final"])
    ap.add_argument("slug", nargs="?")
    ap.add_argument("resto", nargs="*")
    ap.add_argument("--whisper", action="store_true", help="ambiente: carrega o modelo e transcreve 1 s na GPU")
    ap.add_argument("--so", help="transcrever: só este arquivo do mezanino")
    ap.add_argument("--modelo")
    ap.add_argument("--compute-type")
    ap.add_argument("--jargao", choices=["initial_prompt", "hotwords"])
    a = ap.parse_args()
    s = a.slug

    if a.comando == "ambiente":
        from .ambiente import checar, garantir_cuda
        garantir_cuda()
        erros, info = checar(whisper=a.whisper)
        for k, v in info.items():
            print(f"{k}: {v}")
        print("\n".join(f"✗ {e}" for e in erros) or "✓ ambiente completo")
        sys.exit(1 if erros else 0)
    if not s:
        sys.exit("informe o slug do post")
    if a.comando == "ingest":
        from .ingest import ingerir
        tomadas, avisos = ingerir(s)
        for t in tomadas:
            print(f"{t['arquivo']}: {t['largura']}×{t['altura']} {t['fps']} fps{' VFR' if t['vfr'] else ''}"
                  f"{' HDR' if t['hdr'] else ''} {t['duracao']} s → mezanino/{t['mezanino']}")
        print("\n".join(f"! {x}" for x in avisos))
    elif a.comando == "transcrever":
        from .ambiente import garantir_cuda
        garantir_cuda()
        from .transcrever import transcrever
        transcrever(s, a.so, a.modelo, a.compute_type, a.jargao)
        estado(s, situacao="transcrito")
        print(f"→ {projeto(s) / 'transcricao.md'}")
    elif a.comando == "corrigir":
        from .transcrever import corrigir
        arquivo, de, para = a.resto
        print("corrigido" if corrigir(s, arquivo, de, para) else f"não achei “{de}” em {arquivo}")
        if estado(s).get("situacao") in ORDEM[1:]:
            estado(s, situacao="transcrito")
    elif a.comando == "aprovar-transcricao":
        from .transcrever import relatorio
        p = projeto(s) / "transcricao.json"
        tr = ler_json(p)
        tr["aprovada"] = True
        gravar_json(p, tr)
        relatorio(s)
        estado(s, situacao="transcricao-aprovada")
        print("transcrição aprovada")
    elif a.comando == "alinhar":
        exigir(s, "transcricao-aprovada")
        sb, tr, escolha, tl = preparar(s)
        for t, e in escolha.items():
            print(f"{t}: {e['arquivo']} · {e['justificativa']}")
        print(f"duração {tl['duracao']} s · {len(tl['K'])} trechos · {len(tl['C'])} cartões · "
              f"{len(tl['Z'])} zooms · {len(tl['L'])} legendas")
        print("\n".join(f"! {x}" for x in tl["avisos"]))
    elif a.comando in ("previa", "final"):
        exigir(s, "transcricao-aprovada" if a.comando == "previa" else "corte-aprovado")
        destino, folha, falhas, avisos, seg = renderizar(s, a.comando)
        print(f"→ {destino} ({seg} s de render)\n→ {folha}")
        print("\n".join(f"✗ {f}" for f in falhas) or "✓ QA em código sem falhas")
        print("\n".join(f"! {x}" for x in avisos))
        sys.exit(1 if falhas else 0)
    elif a.comando == "aprovar-corte":
        exigir(s, "previa")
        estado(s, situacao="corte-aprovado")
        print("corte aprovado")


if __name__ == "__main__":
    main()
