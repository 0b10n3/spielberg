---
name: spielberg
description: Monta o vídeo D+1 de um post a partir do storyboard.json do hemingway e das tomadas gravadas, com o gate da transcrição e o gate do corte.
disable-model-invocation: true
argument-hint: <slug> [ambiente|ingest|transcrever|corrigir|alinhar|previa|ajuste|final]
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(uv run python -m spielberg *), Bash(uv run python -m unittest *)
---

# /spielberg <slug> [etapa]

Workflow, não agente: cada etapa é um comando determinístico. O modelo só entra para decidir (tomada
repetida, âncora difusa, pedido de ajuste, revisão da folha de quadros), pelo subagent `editor-video`.
Nunca escreva comando ffmpeg à mão: o render monta o filtergraph a partir da timeline.

Sem etapa: continue da situação em `projetos/<slug>/render.json`.

## Etapas

1. **ambiente**: `uv run python -m spielberg ambiente --whisper`. Se falhar, pare e mostre o que falta.
2. **ingest**: as tomadas ficam em `~/Videos/syntaxis/<slug>/brutos/` (o autor copia). Rode
   `uv run python -m spielberg ingest <slug>` e mostre os avisos (HDR, resolução, sem áudio).
3. **transcrever**: `uv run python -m spielberg transcrever <slug>`. Mostre ao autor o
   `projetos/<slug>/transcricao.md`: fala gravada ao lado do roteiro, números em destaque, diferenças.

   **🛑 Transcrição.** O autor confere números e termos. Cada correção:
   `uv run python -m spielberg corrigir <slug> <arquivo.mkv> "de" "para"` (mantém os tempos). Com o ok
   dele: `uv run python -m spielberg aprovar-transcricao <slug>`. Nunca aprove sem o ok explícito.
4. **alinhar**: `uv run python -m spielberg alinhar <slug>`. Âncora difusa ou tomada ambígua → chame o
   `editor-video` com o trecho da transcrição; a decisão vira entrada no `ajustes.yaml`, mostrada antes.
5. **previa**: `uv run python -m spielberg previa <slug>`. Leia o `qa.md` (seção nova) e abra a
   `contact_sheet-previa.png` (Read). Se o QA em código falhar ou a folha mostrar problema, corrija e
   renderize de novo, no máximo 2 vezes, antes de levar ao autor.

   **🛑 Corte.** O autor assiste a `~/Videos/syntaxis/<slug>/previas/vNN.mp4` e pede ajustes por ID
   (K, C, Z, L em `timeline.gerada.yaml`). Até 3 iterações. Para cada pedido, o `editor-video` traduz em
   delta, você mostra o delta, grava em `projetos/<slug>/ajustes.yaml` e roda a prévia de novo.
   Com o ok do autor: `uv run python -m spielberg aprovar-corte <slug>`.
6. **final**: `uv run python -m spielberg final <slug>`. Entrega em `~/Videos/syntaxis/<slug>/saida/`
   o MP4, a capa e o SRT, e marca `render.json` como `entregue`.

## Ajustes por ID (`projetos/<slug>/ajustes.yaml`)

```yaml
C3: {deslocar_inicio_s: -0.5}     # "C3 meio segundo antes"
L14: {texto: "o CDI"}             # "L14 trocar 'CDI' por 'o CDI'"
Z2: {para: 1.06}                  # "Z2 mais suave"
K5: {deslocar_fim_s: 0.2}         # "K5 não corte o fim da palavra"
K7: {remover: true}               # "tirar o trecho K7"
```

Chaves: `deslocar_inicio_s`, `deslocar_fim_s`, `deslocar_s`, `remover`, ou qualquer campo do item
(`texto`, `para`, `eyebrow`, `destaque`). ID que sumiu da timeline gera aviso e não é aplicado.

## Fecho

Commit no spielberg só de texto (`projetos/<slug>/`): `feat(<slug>): vídeo D+1 entregue`. Mídia nunca
entra no git (o teste `Repositorio` reprova). Push só depois do 🛑 da revisão.
