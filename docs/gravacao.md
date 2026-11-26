# Gravação · checklist

Estável entre vídeos. O roteiro de cada vídeo (teleprompter) vem do hemingway:
`posts/<slug>/distribuicao/video/roteiro.md`.

## Câmera

- Vertical, 1080×1920, 30 fps.
- **HDR de vídeo desligado** nos ajustes da câmera. Com HDR ligado o pipeline converte para SDR, mas a
  cor sai pior.
- Celular na altura dos olhos. Olhos perto do terço superior do quadro, abaixo da faixa de ~270 px do
  topo (onde ficam os botões e o nome da conta).
- Rosto e ombros fora da coluna da direita (~130 px), onde ficam curtir, comentar e compartilhar.

## Ambiente

- Mesma luz e mesmo lugar em todas as tomadas. Janela de frente, nunca atrás.
- Parede sem logo de terceiros.
- Uma vez por sessão: 5 s de silêncio total (som ambiente), para referência.

## Cada tomada

- 2 s de silêncio antes de começar e 2 s depois de terminar. A última tomada usa esse silêncio para o
  cartão final.
- Errou? Repita a **tomada inteira**. O pipeline compara as gravações e escolhe a melhor.
- Uma tomada por arquivo. A ordem e o nome dos arquivos não importam: a transcrição diz qual é qual.

## Depois

Copie os arquivos para `~/Videos/syntaxis/<slug>/brutos/` e rode `/spielberg <slug>`.
