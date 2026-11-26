# spielberg

Montagem do vídeo D+1 da Syntaxis: `storyboard.json` (hemingway) + tomadas gravadas → MP4 1080×1920,
capa, SRT e `render.json`. Regras e etapas: `CLAUDE.md`.

## Instalação (uma vez por máquina)

```bash
uv sync                                  # venv isolado com faster-whisper, CTranslate2, cuBLAS/cuDNN 12, Pillow
uv run python scripts/baixar_fontes.py   # só se assets/fonts/ estiver vazio
uv run python -m spielberg ambiente --whisper
```

Registre a guarda de escrita em `.claude/settings.json` (o agente não grava a própria configuração):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit|MultiEdit",
        "hooks": [{ "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/hooks/guarda.py\"" }]
      }
    ]
  }
}
```

## Uso

```bash
# tomadas em ~/Videos/syntaxis/<slug>/brutos/
uv run python -m spielberg ingest <slug>
uv run python -m spielberg transcrever <slug>        # → projetos/<slug>/transcricao.md
uv run python -m spielberg corrigir <slug> <arquivo.mkv> "de" "para"
uv run python -m spielberg aprovar-transcricao <slug>
uv run python -m spielberg previa <slug>             # → previas/vNN.mp4 + qa/contact_sheet-previa.png
uv run python -m spielberg aprovar-corte <slug>
uv run python -m spielberg final <slug>              # → saida/<slug>-d1.mp4, -capa.png, -d1.srt
```

## Contratos

**Lê** `../hemingway/posts/<slug>/distribuicao/video/storyboard.json`, esquema 1.0. Campos usados:
`post`, `formato.duracao_alvo_s`, `tomadas[].fala`, `cenas[]` (`tomada`, `ancora_inicio`, `ancora_fim`,
`cartao`, `zoom`), `capa`, `legenda.palavras_por_bloco_max`. Campos opcionais do cartão que o spielberg
entende além do exemplo do prompt: `rodape`, `segurar_s` (cartão depois da última fala, sobre o silêncio
final) e `ordem` (`["destaque", "texto"]`; padrão: destaque numérico abre o cartão, destaque em palavras
fecha).

**Produz** `projetos/<slug>/render.json`, esquema 1.0 (o uther pode ler, se o autor aprovar):

| Campo | Valor |
|---|---|
| `versao_esquema` | `"1.0"` |
| `situacao` | `transcrito` → `transcricao-aprovada` → `previa` → `corte-aprovado` → `entregue` |
| `versao` | número da última prévia |
| `duracao_s` | duração do último render |
| `caminho_saida` | MP4 final (fora do git) |
| `sha256` | do MP4 final |
| `versao_tokens_marca` | `$extensions["br.com.syntaxis"].version` dos tokens |
| `gerado_em` | ISO 8601 com fuso |

## Testes

```bash
uv run python -m unittest discover -s tests -t .
```
