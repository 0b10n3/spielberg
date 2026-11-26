"""Uma checagem por regra: corte, ajustes por ID, números, zona segura, ingest e repositório.
Rodar: uv run python -m unittest discover -s tests"""
import subprocess
import tempfile
import unittest
from pathlib import Path

import spielberg
from spielberg import CFG, RAIZ, cortar, ingest, qa, timeline
from tests import sintetico as S

SB = {"versao_esquema": "1.0", "formato": {"duracao_alvo_s": [1, 60]}, "legenda": {"palavras_por_bloco_max": 4},
      "tomadas": [{"id": "T1", "bloco": "gancho", "fala": "Em cinco semanas o prefixado caiu. E a Selic parada."}],
      "cenas": [{"id": "S1", "tomada": "T1", "ancora_inicio": "Em cinco semanas", "ancora_fim": "prefixado caiu.",
                 "visual": "camera", "cartao": {"id": "C1", "modo": "sobreposto", "chassi": "B", "destaque": "−3,6%"}},
                {"id": "S2", "tomada": "T1", "ancora_inicio": "E a Selic", "ancora_fim": "Selic parada.",
                 "visual": "camera", "zoom": {"de": 1.0, "para": 1.1, "alvo": "rosto"}}]}
FALA = [(0.5, 2.0, "Em cinco semanas o prefixado caiu."), (3.0, 4.2, "E a Selic parada.")]
TR = {"arquivos": {"t1.mkv": {"duracao": 5.0, "palavras": S.palavras(FALA)}}}
ESC = {"T1": {"arquivo": "t1.mkv"}}


class Corte(unittest.TestCase):
    def test_corta_so_em_silencio_medido_e_fora_das_palavras(self):
        pal = S.palavras(FALA)
        k = cortar.trechos(pal, [(2.0, 3.0)])
        c = CFG["corte"]
        self.assertEqual(len(k), 2)
        self.assertAlmostEqual(k[0][1], 2.0 + c["margem_depois_s"], places=3)
        self.assertAlmostEqual(k[1][0], 3.0 - c["margem_antes_s"], places=3)
        fins = {p["fim"] for p in pal}
        for a, b in k:  # nenhum limite de trecho cai dentro de uma palavra
            self.assertFalse(any(p["ini"] < a < p["fim"] or p["ini"] < b < p["fim"] for p in pal), (a, b, fins))

    def test_pausa_sem_silencio_medido_nao_corta(self):
        self.assertEqual(len(cortar.trechos(S.palavras(FALA), [])), 1)

    def test_pausa_abaixo_do_limiar_nao_corta(self):
        curta = [(0.5, 2.0, "Em cinco semanas"), (2.2, 3.0, "o prefixado")]
        self.assertEqual(len(cortar.trechos(S.palavras(curta), [(2.0, 2.2)])), 1)

    def test_silencedetect_acha_a_pausa_do_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = S.tomada(Path(tmp) / "t.mkv", FALA, 5)
            sil = cortar.silencios(arq)
            self.assertTrue(any(a <= 2.1 and b >= 2.9 for a, b in sil), sil)


class Ajustes(unittest.TestCase):
    def gerar(self, ajustes=None):
        return timeline.gerar("x", SB, TR, ESC, ajustes, sil={"t1.mkv": [(2.0, 3.0)]})

    def test_ajuste_por_id_sobrevive_a_nova_geracao(self):
        base = self.gerar()
        aj = {"C1": {"deslocar_inicio_s": 0.5}, "Z1": {"para": 1.06}, "L1": {"texto": "Em 5 semanas"}}
        um, dois = self.gerar(aj), self.gerar(aj)
        self.assertEqual(um, dois)  # mesma entrada, mesma timeline
        self.assertAlmostEqual(um["C"][0]["ini"], base["C"][0]["ini"] + 0.5, places=3)
        self.assertEqual(um["Z"][0]["para"], 1.06)
        self.assertEqual(um["L"][0]["texto"], "Em 5 semanas")

    def test_id_inexistente_avisa_e_nao_aplica(self):
        tl = self.gerar({"C9": {"deslocar_inicio_s": -1}})
        self.assertTrue(any("C9" in a for a in tl["avisos"]))

    def test_corte_remove_a_pausa_do_relogio_final(self):
        tl = self.gerar()
        self.assertEqual(len(tl["K"]), 2)
        self.assertLess(tl["duracao"], 4.2 - 0.5 + 0.3)
        self.assertLessEqual(tl["S"][1]["ini"], tl["K"][0]["fim"] - tl["K"][0]["ini"] + 0.11)

    def test_legenda_nao_atravessa_frase(self):
        for b in self.gerar()["L"]:
            self.assertLessEqual(len(b["texto"].split()), 4)
            self.assertFalse(any(w.endswith(".") for w in b["texto"].split()[:-1]), b["texto"])


class Numeros(unittest.TestCase):
    def test_normalizacao(self):
        self.assertEqual(qa.numeros("R$ 13.405 e 12,40% e 10 mil reais em 13/10/2026 no Prefixado 2029"),
                         {"13405", "12.4%", "10000"})

    def test_numero_fora_do_post_ou_nao_falado_reprova(self):
        f = qa.checar_numeros([("C1", "Selic: 13,75% · 99%")], "Selic em 13,75%.", "a selic de 13,75%")
        self.assertEqual(len(f), 2)
        self.assertTrue(all("99%" in x for x in f))

    def test_numero_no_post_e_falado_passa(self):
        self.assertEqual(qa.checar_numeros([("C6", "R$ 10 MIL · R$ 13.405")], "R$ 10 mil ... R$ 13.405",
                                           "10 mil reais viram 13.405"), [])


class ZonaSegura(unittest.TestCase):
    Z, F = (72, 270, 950, 1500), (1150, 1400)

    def test_caixa_fora_da_zona_reprova(self):
        f = qa.checar_caixas([("C1", "cartao", [{"tipo": "texto", "texto": "x", "caixa": [60, 300, 500, 360]}])], self.Z, self.F)
        self.assertTrue(f and "zona segura" in f[0])

    def test_cartao_na_faixa_da_legenda_reprova(self):
        f = qa.checar_caixas([("C2", "cartao", [{"tipo": "texto", "texto": "x", "caixa": [100, 1100, 500, 1180]}])], self.Z, self.F)
        self.assertTrue(f and "faixa da legenda" in f[0])

    def test_assinatura_da_capa_fica_abaixo_da_zona_por_regra_da_marca(self):
        ok = [("capa", "capa", [{"tipo": "assinatura", "texto": "@syntaxis", "caixa": [72, 1590, 400, 1660]}])]
        self.assertEqual(qa.checar_caixas(ok, self.Z, self.F), [])

    def test_cartao_real_cabe_na_zona(self):
        from spielberg import cartoes, legendas
        with tempfile.TemporaryDirectory() as tmp:
            S.usar_midia(tmp)
            c = {"modo": "cheio", "chassi": "C", "eyebrow": "R$ 10 MIL · SELIC PARADA EM 13,75% ATÉ 2029",
                 "texto": "Tesouro Selic: R$ 13.081\nPrefixado: R$ 13.405", "destaque": "Perde se a Selic média passar de ~15%",
                 "rodape": "valores brutos, cálculo próprio"}
            caixas = cartoes.cartao(c, Path(tmp) / "c.png", legendas.faixa())
            self.assertEqual(qa.checar_caixas([("C6", "cartao", caixas)], self.Z, legendas.faixa()), [])


class Ingest(unittest.TestCase):
    def test_detecta_hdr_hlg_e_converte(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = S.tomada(Path(tmp) / "hdr.mov", [(0.2, 0.8)], 1,
                           ["-vf", "setparams=color_trc=arib-std-b67:color_primaries=bt2020:colorspace=bt2020nc"])
            info = ingest.sondar(arq)
            self.assertTrue(info["hdr"])
            spielberg.rodar(["ffmpeg", "-y", "-v", "error", "-i", arq, "-vf", ingest.filtro_video(info),
                             "-t", "0.5", "-f", "null", "-"])

    def test_detecta_fps_variavel(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = Path(tmp) / "vfr.mp4"
            spielberg.rodar(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=1",
                             "-f", "lavfi", "-i", "testsrc2=s=320x240:r=15:d=1",
                             "-filter_complex", "[0:v][1:v]concat=n=2:v=1", "-fps_mode", "vfr", arq])
            self.assertTrue(ingest.sondar(arq)["vfr"])


class Repositorio(unittest.TestCase):
    def test_nenhuma_midia_nem_arquivo_grande_no_git(self):
        r = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           cwd=RAIZ, capture_output=True, text=True)
        limite = CFG["git"]["max_arquivo_mb"] * 1024 * 1024
        midia = {".mp4", ".mov", ".mkv", ".wav", ".m4a", ".aac", ".mp3", ".png", ".jpg"}
        for nome in filter(None, r.stdout.split("\0")):
            p = RAIZ / nome
            self.assertNotIn(p.suffix.lower(), midia, nome)
            if p.exists():
                self.assertLessEqual(p.stat().st_size, limite, nome)



class Guarda(unittest.TestCase):
    def rodar(self, alvo):
        import json
        entrada = json.dumps({"tool_name": "Write", "tool_input": {"file_path": alvo}, "cwd": str(RAIZ)})
        return subprocess.run(["python3", str(RAIZ / "hooks/guarda.py")], input=entrada, text=True,
                              capture_output=True).returncode

    def test_bloqueia_hemingway_e_marca_e_libera_o_repo(self):
        self.assertEqual(self.rodar("../hemingway/posts/x/distribuicao/video/storyboard.json"), 2)
        self.assertEqual(self.rodar("../../brand/tokens/syntaxis.tokens.json"), 2)
        self.assertEqual(self.rodar("projetos/x/ajustes.yaml"), 0)


if __name__ == "__main__":
    unittest.main()
