# Monitor de palavras-chave do Telegram

Escuta os grupos e canais em que **você já está**, procura os termos que você cadastrar e te manda uma notificação privada só quando algo bate. A ideia é silenciar todos os grupos no app e deixar apenas a conversa com o bot notificando.

---

## Sumário

1. [Como funciona](#1-como-funciona)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Passo 1 — Credenciais MTProto](#3-passo-1--credenciais-mtproto)
4. [Passo 2 — Bot notificador](#4-passo-2--bot-notificador)
5. [Passo 3 — Instalação](#5-passo-3--instalação)
6. [Passo 4 — Configurar o .env](#6-passo-4--configurar-o-env)
7. [Passo 5 — Gerar a sessão](#7-passo-5--gerar-a-sessão)
8. [Passo 6 — Rodar](#8-passo-6--rodar)
9. [Passo 7 — Silenciar os grupos](#9-passo-7--silenciar-os-grupos-o-passo-que-faz-tudo-valer)
10. [Comandos](#10-comandos)
11. [Como o casamento de termos funciona](#11-como-o-casamento-de-termos-funciona)
12. [Ajustes finos](#12-ajustes-finos)
13. [Deploy 24/7](#13-deploy-247)
14. [Segurança](#14-segurança)
15. [Problemas comuns](#15-problemas-comuns)
16. [Limitações e próximos passos](#16-limitações-e-próximos-passos)

---

## 1. Como funciona

São duas contas do Telegram trabalhando juntas, com papéis diferentes:

| Peça | O que é | Papel |
|---|---|---|
| **Listener** | Sua conta pessoal, via Telethon (MTProto) | Lê tudo que você já lê: grupos, supergrupos e canais |
| **Notificador** | Um bot do @BotFather | Te manda a DM e recebe seus comandos |

**Por que não usar só um bot?** Um bot da Bot API só lê mensagens de grupos onde ele foi adicionado manualmente por alguém com permissão — e em canais ele precisa ser administrador. Como você não é dono dos canais de terceiros, isso é inviável. A conta pessoal (userbot) não tem essa restrição: ela enxerga exatamente o que você enxerga.

Fluxo de uma mensagem:

```
mensagem chega no grupo/canal
        ↓
  normalização  (minúsculas, sem acento, sem pontuação)
        ↓
  match exato → não bateu? → match aproximado (typo)
        ↓
  deduplicação (mesmo anúncio repostado em 5 grupos = 1 alerta)
        ↓
  limite de alertas por hora (anti-flood)
        ↓
  DM no seu privado com o trecho + link da mensagem original
```

---

## 2. Pré-requisitos

- **Python 3.10+** (ou Docker, se preferir)
- Uma conta do Telegram com número de telefone ativo
- Estar dentro dos grupos/canais que quer monitorar
- Opcional, para rodar 24/7: uma VPS, um Raspberry Pi, ou o free tier da Oracle Cloud

Consumo é baixíssimo — roda tranquilo em 512 MB de RAM.

---

## 3. Passo 1 — Credenciais MTProto

1. Acesse **https://my.telegram.org** e faça login com seu número.
2. Entre em **API development tools**.
3. Preencha o formulário:
   - *App title*: `alerta pessoal` (qualquer nome)
   - *Short name*: `alertapessoal`
   - *Platform*: Desktop
4. Anote o **`api_id`** (número) e o **`api_hash`** (string longa).

> Esse par identifica o aplicativo, não a sua conta. Ainda assim, não publique em lugar nenhum.

---

## 4. Passo 2 — Bot notificador

1. No Telegram, abra **@BotFather**.
2. Envie `/newbot` e siga as instruções (nome + username terminando em `bot`).
3. Anote o **token** (formato `123456789:AAA...`).
4. **Abra uma conversa com o seu bot recém-criado e mande `/start`.** Sem isso o Telegram bloqueia o envio de mensagens para você — é a regra de que bots não podem iniciar conversa.

> Não precisa mexer em privacy mode aqui. Esse bot nunca vai entrar em grupo nenhum; ele só fala com você.

---

## 5. Passo 3 — Instalação

```bash
cd tg-alert

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Estrutura dos arquivos:

```
tg-alert/
├── app/
│   ├── main.py        # entrypoint: listener + loop de comandos
│   ├── config.py      # leitura e validação do .env
│   ├── db.py          # SQLite: termos, dedupe, rate limit
│   ├── matcher.py     # normalização e casamento de termos
│   ├── notifier.py    # cliente da Bot API
│   ├── login.py       # gera a sessão (rodar uma vez)
│   └── whoami.py      # descobre seu user id
├── data/              # criado automaticamente (sessão + banco)
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── tg-alert.service   # unit do systemd
```

---

## 6. Passo 4 — Configurar o .env

```bash
cp .env.example .env
```

Abra o `.env` e preencha:

```ini
TG_API_ID=1234567
TG_API_HASH=seu_api_hash
TG_BOT_TOKEN=123456789:AAA...
TG_OWNER_ID=              # deixe em branco por enquanto
```

O `TG_OWNER_ID` é o seu id numérico — é o que impede que outra pessoa mande comandos pro seu bot. Você vai descobri-lo no próximo passo.

---

## 7. Passo 5 — Gerar a sessão

Esta etapa é **interativa** e roda **uma única vez**:

```bash
cd app
python login.py
```

Vai pedir, nesta ordem:

1. Seu telefone com código do país: `+5551999999999`
2. O código que chega **dentro do Telegram** (não por SMS, na maioria dos casos)
3. Sua senha de verificação em duas etapas, se você tiver uma

No final ele imprime seu id. Copie para o `.env`:

```ini
TG_OWNER_ID=987654321
```

Se precisar consultar de novo depois: `python whoami.py`.

Isso cria `data/user.session`. **Esse arquivo é o seu login** — enquanto ele existir, você não precisa autenticar de novo.

---

## 8. Passo 6 — Rodar

```bash
cd app
python main.py
```

Saída esperada:

```
[ok] conectado como Seu Nome (id 987654321)
```

Você recebe uma DM do bot confirmando que ligou. Cadastre o primeiro termo mandando pro bot:

```
/add armani code
```

E teste sem esperar anúncio real:

```
/test promo ARMANICODE 125ml
```

Se responder que casaria, está tudo certo.

---

## 9. Passo 7 — Silenciar os grupos (o passo que faz tudo valer)

O software só resolve metade do problema. A outra metade é de configuração no app:

1. Entre em cada grupo/canal de perfume → **Mutar / Desativar notificações** → *Sempre*.
2. Abra a conversa com o seu bot → garanta que as notificações estão **ligadas**.
3. Opcional: fixe a conversa do bot no topo da lista.

Pronto — o único que toca no seu celular é o bot, e só com o que você cadastrou.

---

## 10. Comandos

Todos são enviados na conversa privada com o seu bot:

| Comando | O que faz |
|---|---|
| `/add termo` | Cadastra uma palavra-chave |
| `/list` | Lista os termos com seus ids |
| `/del 3` | Remove pelo id mostrado no `/list` |
| `/test texto` | Simula uma mensagem e mostra o que casaria |
| `/stats` | Quantos alertas por termo nas últimas 24h |
| `/pause` | Para de notificar (continua rodando) |
| `/resume` | Volta a notificar |
| `/help` | Ajuda |

Nada é hardcoded — dá pra gerenciar tudo do celular sem tocar em código.

---

## 11. Como o casamento de termos funciona

**Normalização.** Antes de comparar, o texto vira minúsculas, perde acentos e pontuação, e os espaços são colapsados:

```
"ARMANI-CODE!!!  Absolu"  →  "armani code absolu"
```

**Match exato.** Usa regex com fronteira de palavra e espaço opcional entre os termos. Cadastrando `armani code`, ele pega:

- `ARMANI CODE 125ml` ✅
- `armani-code absolu` ✅
- `Armanicode edp` ✅ (grudado)
- `armani   code` ✅ (espaço duplo)
- `Codename armani` ❌ (fronteira de palavra evita o falso positivo)

**Match aproximado.** Se o exato não bater, compara janelas de palavras por similaridade. Cobre erro de digitação do vendedor:

- `ARMANI COD 100ml` → 95% ✅
- `armnai code promo` → 90% ✅

Alertas aproximados chegam marcados com 🔎 e o percentual; os exatos vêm com 🎯. Assim você sabe na hora se é certeza ou palpite.

**O que ele não faz:** ordem invertida. `Sauvage da Dior` **não** casa com o termo `dior sauvage`. Se isso importar, cadastre as duas ordens, ou cadastre só a palavra mais distintiva (`sauvage`).

---

## 12. Ajustes finos

No `.env`:

| Variável | Padrão | O que faz |
|---|---|---|
| `FUZZY_THRESHOLD` | `88` | Similaridade mínima do match aproximado. Abaixar → mais alertas e mais falso positivo. Subir para `92` deixa mais rigoroso. |
| `DEDUPE_TTL_HOURS` | `6` | Por quanto tempo um texto idêntico é ignorado. Anúncio repostado em 5 grupos vira 1 alerta. |
| `MAX_ALERTS_PER_HOUR` | `12` | Teto por termo. Protege de spam — se alguém floodar, você não leva 200 DMs. |
| `SNIPPET_CHARS` | `400` | Tamanho do trecho na notificação. |

**Estratégia de cadastro.** Comece específico (`armani code`) e observe uns dias com `/stats`. Se estiver recebendo pouco, afrouxe para o termo mais curto e distintivo. Se estiver recebendo demais, especifique mais (`armani code parfum`).

---

## 13. Deploy 24/7

### Opção A — Docker (recomendado)

A sessão precisa ser gerada interativamente antes:

```bash
docker compose run --rm monitor python login.py
```

Depois preencha o `TG_OWNER_ID` no `.env` e suba:

```bash
docker compose up -d
docker compose logs -f
```

O volume `./data` mantém sessão e banco entre reinícios — **não apague essa pasta**.

### Opção B — systemd

Edite `tg-alert.service` trocando `SEU_USUARIO` pelo seu usuário e ajustando os caminhos, depois:

```bash
sudo cp tg-alert.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tg-alert
sudo systemctl status tg-alert
journalctl -u tg-alert -f      # acompanhar os logs
```

### Onde hospedar

- **Oracle Cloud Free Tier** — VM gratuita permanente, mais que suficiente
- **VPS barata** — Contabo, Hetzner, Racknerd
- **Raspberry Pi em casa** — funciona bem; só garanta que não desligue

---

## 14. Segurança

⚠️ **`data/user.session` dá acesso total à sua conta do Telegram.** Quem tiver esse arquivo entra como você.

- Nunca comite no Git (o `.gitignore` já cobre, mas confira antes do primeiro push)
- Não jogue em Google Drive, Dropbox ou pastelbin
- Em VPS compartilhada: `chmod 600 data/user.session`
- Se vazar: Telegram → **Configurações → Dispositivos → Encerrar todas as outras sessões**

O `.env` também merece o mesmo cuidado — o token do bot está lá.

**Sobre a política do Telegram:** userbots são tolerados desde que não façam spam, mass-add ou scraping em escala. O seu só lê passivamente e manda DM pra você mesmo — risco baixo. O que dá problema é usar a conta pra enviar em massa.

---

## 15. Problemas comuns

**`Unauthorized` ao mandar a DM**
Você não iniciou conversa com o bot. Abra o chat dele e mande `/start`.

**`chat not found`**
O `TG_OWNER_ID` está errado. Rode `python whoami.py` e corrija.

**Não recebo nada, mas o bot está rodando**
Cheque na ordem: (1) `/list` tem termos? (2) `/test <texto real do anúncio>` casa? (3) não está `/pause`? (4) o texto do anúncio está mesmo no texto/legenda e não *dentro* da imagem?

**Recebo o mesmo anúncio várias vezes**
São textos ligeiramente diferentes (o dedupe é por texto exato normalizado). Aumente `DEDUPE_TTL_HOURS` ou cadastre termos mais específicos.

**`FloodWaitError` no log**
O Telethon já espera sozinho. Só é sinal de problema se acontecer o tempo todo.

**Sessão expirou / pede login de novo**
Você encerrou a sessão pelo app, ou o arquivo foi perdido. Rode `python login.py` de novo.

**Link "Abrir mensagem original" não aparece**
Grupos legados (não-supergrupos) não têm link de mensagem. Normal — o trecho do texto continua vindo.

---

## 16. Limitações e próximos passos

**Texto dentro da imagem.** Muito vendedor coloca preço e nome só na arte, sem legenda. O bot não enxerga isso. Antes de investir em OCR, confira uns 10 posts recentes dos seus canais para saber se é o seu caso. Se for, o caminho é baixar a foto com `event.download_media()` e passar por `pytesseract` — dá pra adicionar em cima da estrutura atual sem reescrever nada.

**Ideias para depois:**

- Filtro de preço máximo (regex de `R$ xxx` no texto, alerta só abaixo do teto)
- Lista de grupos permitidos, em vez de escutar todos
- Blocklist de termos (`/block réplica` para ignorar anúncios de falsificado)
- Botão inline "silenciar esse termo por 24h" direto na notificação
- Histórico dos anúncios num CSV, pra acompanhar variação de preço
