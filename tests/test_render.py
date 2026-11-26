"""Integração: tomadas sintéticas → cartões, legendas, prévia e final, conferidos pelo QA."""
import tempfile
import unittest
from pathlib import Path

from spielberg import cartoes, cortar, legendas, qa, render, timeline
from spielberg.marca import zona_segura
from tests import sintetico as S
from tests.test_regras import SB, TR


class Render(unittest.TestCase):
    def test_previa_e_final_saem_nas_especificacoes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            S.usar_midia(tmp)
            mez = tmp / "mezanino"
            mez.mkdir()
            from tests.test_regras import FALA
            arq = S.tomada(mez / "t1.mkv", FALA, 5)
            sil = {"t1.mkv": cortar.silencios(arq)}
            tl = timeline.gerar("x", SB, TR, {"T1": {"arquivo": "t1.mkv"}}, sil=sil)
            itens = []
            for c in tl["C"]:
                c["png"] = f"{c['id']}.png"
                itens.append((c["id"], "cartao", cartoes.cartao(c, tmp / c["png"], legendas.faixa())))
            for b in tl["L"]:
                b["png"] = f"{b['id']}.png"
                itens.append((b["id"], "legenda", legendas.bloco(b["texto"], tmp / b["png"])))
            self.assertEqual(qa.checar_caixas(itens, zona_segura(), legendas.faixa()), [])
            cc = legendas.concat(tl["C"], tl["duracao"], tmp, "cartoes")
            lc = legendas.concat(tl["L"], tl["duracao"], tmp, "legendas")
            for modo in ("previa", "final"):
                destino = tmp / f"{modo}.mp4"
                segundos, _ = render.montar(tl, mez, cc, lc, destino, modo)
                checks, dur = qa.especificacoes(destino, modo, [1, 60])
                self.assertEqual([c for c in checks if not c[1]], [], modo)
                self.assertAlmostEqual(dur, tl["duracao"], delta=0.1)
            loud = qa.loudness(tmp / "final.mp4")
            self.assertLessEqual(abs(loud["I"] - (-14)), 1.0, loud)


if __name__ == "__main__":
    unittest.main()
