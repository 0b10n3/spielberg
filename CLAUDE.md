# spielberg: montagem do vídeo D+1 da Syntaxis

Recebe o `storyboard.json` do hemingway e as tomadas gravadas no celular. Entrega o MP4 final, a capa,
o SRT e o `render.json`. Roda local: ffmpeg + Pillow + faster-whisper na GPU. Português do Brasil.

## Regras invioláveis

1. **Workflow antes de agente.** Cada etapa é código. O modelo só decide: tomada repetida, âncora
   difusa, pedido de ajuste, revisão da folha de quadros (subagent `editor-video`).
2. **Timeline como código.** O render monta o filtergraph a partir de `timeline.gerada.yaml` +
   `ajustes.yaml`. **Ninguém escreve comando ffmpeg à mão.** Mesma entrada, mesmo vídeo.
3. **O áudio manda.** Tempos vêm das palavras do Whisper e do `silencedetect`, nunca de estimativa.
   Cenas ancoram em trechos literais da fala.
4. **Mídia nunca entra no git.** Vídeo, áudio e PNG ficam em `~/Videos/syntaxis/<slug>/`. O teste
   `Repositorio` reprova mídia ou arquivo acima de 5 MB.
5. **Transcrição só local.** Nenhum serviço de transcrição em nuvem.
6. **Só leitura:** `../hemingway/` (posts e storyboard) e `../../brand/` (tokens, LOGO, SOCIAL.md).
   Valores de marca vêm dos tokens por script. O que ainda não está nos tokens fica em
   `config/spielberg.yaml` → `marca_fora_dos_tokens`, com a fonte. Contradição entre documentos de marca
   é relatada, nunca resolvida aqui.
7. **Nenhum número novo.** Todo número na tela está no post e na transcrição aprovada (QA reprova).
8. **Educação, não recomendação.** Nenhum vídeo sugere compra de ativo ou emissor (manual ANBIMA).
9. **Sem trilha no arquivo.** Música, se houver, entra no app de cada rede.
10. **Gates:** a transcrição e o corte só avançam com o ok explícito do autor.

## Etapas (`uv run python -m spielberg <comando> <slug>`)

| # | Comando | Faz |
|---|---|---|
| 0 | `ambiente [--whisper]` | ffmpeg, filtros, GPU, CUDA, fontes, tokens |
| 1 | `ingest` | ffprobe (rotação, VFR, HDR) → mezanino 1080×1920, 30 fps, BT.709, 48 kHz; copia o storyboard com sha256 |
| 2 | `transcrever` | faster-whisper com tempo por palavra → `transcricao.json`/`.md` |
| 🛑 | `corrigir` / `aprovar-transcricao` | autor confere números e termos |
| 3 | `alinhar` | atribui arquivo → tomada, escolhe a melhor repetição, acha âncoras, gera a timeline |
| 4–8 | `previa` | corta pausas, cartões, legendas, render 540×960, QA em código, folha de quadros |
| 🛑 | `aprovar-corte` | autor assiste e pede ajustes por ID (até 3 iterações) |
| 9 | `final` | render 1080×1920 com loudnorm em 2 passadas, capa, SRT, `render.json` = `entregue` |

Orquestração: `/spielberg <slug> [etapa]` (`.claude/skills/spielberg/SKILL.md`).

## Onde fica cada coisa

| O quê | Onde |
|---|---|
| Parâmetros (fonte única) | `config/spielberg.yaml`; caminhos da máquina em `config/local.yaml` (fora do git) |
| Código | `spielberg/` (`ambiente`, `ingest`, `transcrever`, `alinhar`, `cortar`, `marca`, `cartoes`, `legendas`, `timeline`, `render`, `qa`) |
| Projeto do vídeo (só texto, versionado) | `projetos/<slug>/`: storyboard, ingest, transcrição, timeline, ajustes, qa.md, render.json |
| Mídia (fora do git) | `~/Videos/syntaxis/<slug>/`: brutos, mezanino, cartoes, previas, qa, saida |
| Fontes da marca (OFL) | `assets/fonts/` (`scripts/baixar_fontes.py`) |
| Gravação | `docs/gravacao.md` |
| Decisões técnicas com fonte | `docs/pesquisa.md` |
| Guarda de escrita | `hooks/guarda.py` (registrar em `.claude/settings.json`: ver README) |

## Testes

`uv run python -m unittest discover -s tests -t .` (vídeo sintético do `lavfi`; ~10 s).

## Git

- Repo próprio: `git@github.com:0b10n3/spielberg.git`.
- Commit: `<tipo>(<escopo>): <o que mudou, no imperativo>`. Tipos: `feat`, `fix`, `docs`, `chore`,
  `refactor`. Escopos: `pipeline`, `config`, `qa`, `docs`, ou o slug do vídeo.
- Push só depois do 🛑 da revisão. Nunca `--force`. Antes de commitar, confira que nada de chave, token
  ou mídia entrou no diff.
