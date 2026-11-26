# Pesquisa · decisões técnicas do spielberg

Cada linha: o achado, a fonte (oficial, terceiros ou medição local), a data da consulta e a decisão.
"Regra do projeto" = valor inicial sem fonte externa, a calibrar na avaliação (Fase 3).

## Ambiente medido (25/11/2026)

| Item | Achado | Fonte | Decisão |
|---|---|---|---|
| ffmpeg | 8.0.1 com libx264, libass, libfreetype, libfontconfig, libharfbuzz, libfribidi, libzimg; encoder `h264_nvenc`; filtros zscale, tonemap, libplacebo, loudnorm, ebur128, blackdetect, freezedetect, silencedetect, subtitles (`fontsdir`), overlay; decoder librsvg | `ffmpeg -buildconf/-filters/-encoders/-decoders` local | Etapa 0 confere libx264, libzimg, librsvg e os filtros usados |
| GPU | RTX 3050 Laptop, 6 GB, driver 595.99 (CUDA 13.2) | `nvidia-smi` | CTranslate2 com runtime CUDA 12 rodou neste driver (etapa 0 `--whisper`, 25/11) |
| Velocidade | 80 s sintéticos: prévia 540×960 libx264 veryfast 3,6 s; NVENC p1 2,7 s; final 1080×1920 libx264 medium CRF 18 15,8 s | medição local | NVENC não adotado: ganho irrelevante (corte 1 da ordem de corte) |
| Python | 3.14.4 + uv 0.11.26; wheels cp314 de ctranslate2 4.9.1, onnxruntime 1.32, av 19.0.2, tokenizers 0.23.3, numpy 2.5.5 | PyPI (25/11) | Venv do uv com o Python do sistema |

## Transcrição

| Item | Achado | Fonte | Decisão |
|---|---|---|---|
| Versões | faster-whisper 1.2.1 (31/10/2025); ctranslate2 4.9.1 (22/11/2026, "CUDA 12 release builds") | PyPI; GitHub OpenNMT/CTranslate2 releases | Fixadas no `pyproject.toml` |
| CUDA | "The latest versions of ctranslate2 only support CUDA 12 and cuDNN 9"; instalar `nvidia-cublas-cu12` e `nvidia-cudnn-cu12==9.*`; `LD_LIBRARY_PATH` antes de abrir o Python | README do SYSTRAN/faster-whisper (oficial) | Libs no venv; `ambiente.garantir_cuda()` define a variável e reexecuta o comando |
| Modelo | Aceita `large-v3`, `large-v3-turbo`/`turbo`. VRAM (issue #1030, GPU não informada): large-v3 fp16 4521 MB, int8 2953 MB; turbo fp16 2537 MB, int8 1545 MB | transcribe.py (master); issue #1030 | Padrão `large-v3-turbo` float16. **Pendente:** comparar com `large-v3` int8_float16 na T1 real, nos termos do glossário |
| Jargão | `initial_prompt` e `hotwords` existem; `hotwords` sem efeito com `prefix` | docstring de `transcribe()` | Padrão `initial_prompt` com o glossário tirado das falas do roteiro. **Pendente:** comparar com `hotwords` na T1 |
| VAD | Padrões do `VadOptions`: threshold 0,5, min_silence 2000 ms, speech_pad 400 ms | vad.py (master) | `vad_filter: true` com os padrões |
| Tempo por palavra | Vem de DTW sobre a cross-attention; o mantenedor recomenda alinhamento forçado para tempos melhores | issue #1030 (comentário de 02/10/2024) | O corte só acontece em silêncio medido pelo `silencedetect`, com margem; sem WhisperX nesta fase |

## Edição e render

| Item | Achado | Fonte | Decisão |
|---|---|---|---|
| Referência | video-use: transcrição primeiro (ElevenLabs, nuvem), EDL em `edl.json`, `timeline_view` só em ponto de decisão, fade de 30 ms em todo corte, nunca dentro de palavra, margem 30–200 ms, silêncio ≥ 400 ms = corte limpo, 150–400 ms conferir, < 150 ms inseguro, até 3 autoavaliações | github.com/browser-use/video-use README e SKILL.md (MIT) | Ideias adotadas sem dependência (transcrição em nuvem é proibida aqui). Limiar 400 ms, margens 100/80 ms, fade 30 ms |
| Legenda | PNG via Pillow numa sequência `concat` em vez de ASS/libass | decisão de implementação (25/11) | A caixa é medida com a mesma fonte que desenha (sem diferença de métrica Pillow × libass) e a fonte variável da marca funciona sem a busca de fontes do libass. Muda o plano aprovado (que dizia ASS) |
| Cartões | PNG do quadro inteiro, uma sequência `concat` (um cartão por vez) + `overlay` | decisão de implementação | Dois overlays no total (cartões e legendas), seja qual for o número de itens |
| Cor | Opções de saída `-color_*` não chegaram ao VUI do x264 no ffmpeg 8 (teste reprovou); `setparams` nos quadros resolveu | teste `test_render` (25/11) | `setparams=…bt709` no fim do mezanino e do render |
| Símbolo | librsvg no ffmpeg com só `-width` deixa a altura padrão e o glifo encolhe; com `-width` + `-height` + `keep_ar` sai certo | medição local (25/11) | `marca.simbolo()` passa os três |
| Zoom | Tremor do `zoompan` (arredondamento) não confirmado em fonte | — | Modo `corte` (punch-in seco, escala constante por cena): sem tremor por construção. Rampa só depois de pesquisa (S2) |
| HDR | iPhone grava HLG (`arib-std-b67`) | ffprobe | zscale → linear → tonemap hable → BT.709; aviso para regravar sem HDR |
| Loudness | Nenhuma plataforma publica alvo oficial nas páginas lidas | — | −14 LUFS, −1 dBTP, LRA 11, duas passadas com `linear=true` no final (regra do projeto) |

## Plataformas (25/11/2026)

| Plataforma | Achado | Fonte |
|---|---|---|
| YouTube | MP4; H.264 High progressivo 4:2:0, CABAC; AAC-LC ou Opus 48 kHz estéreo; BT.709; 8 Mbps em 1080p30 | support.google.com/youtube/answer/1722171 (oficial) |
| Shorts | Até 3 min; até 1080p | support.google.com/youtube/answer/10059070 (oficial) |
| LinkedIn | 3 s a 15 min; até 5 GB; 10–60 fps; proporção 1:2.4 a 2.4:1 | linkedin.com/help/linkedin/answer/a548372 (oficial; página de ~2 anos) |
| Reels | Duração, tamanho e loudness **a confirmar**: as páginas oficiais não renderizaram sem navegador | help.instagram.com; facebook.com/business/help |
| Zona de anúncio | ~14% topo, ~35% base, ~6% laterais, atribuídos ao Ads Guide da Meta | lilachbullock.com/instagram-reels-safe-zone (terceiros, out/2026): **confirmar** no Gerenciador de Anúncios |
| Zona orgânica | x 72–950, y 270–1500 | `brand/tokens` `social.safeZone` e `brand/SOCIAL.md` §2 (topo: Meta oficial; base e direita: `[VERIFICAR]` na própria marca) |

## Vídeo curto educativo

Sem fonte boa nesta rodada. Regras do projeto, a calibrar: gancho em até 3 s, troca visual a cada 5 s
ou menos, legenda queimada sempre, duração-alvo do storyboard.
