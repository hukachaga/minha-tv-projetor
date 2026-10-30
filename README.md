# Minha TV: projetor Byintek U90 Max sem anúncios

Uma tela inicial leve e sem anúncios para o Google TV do projetor **Byintek U90 Max**. Ela tem o meu plano de fundo,
os 5 apps que eu uso e uma fileira com os vídeos novos dos canais que eu sigo no YouTube, sem Shorts. Essa fileira é
montada por um serviço que roda numa LXC do meu Proxmox.

Este projeto é uma adaptação do [Free My TV](https://github.com/simbasjungles/free-my-tv) (licença MIT), um launcher de
código aberto para Google TV.

## O que tem aqui

| Caminho | O que é |
|---|---|
| [`apk/FreeMyTV-Byintek-U90Max.apk`](apk/) | O app pronto para instalar, já configurado para este projetor (com o SHA-256 ao lado) |
| [`free-my-tv-byintek.patch`](free-my-tv-byintek.patch) | Todas as minhas mudanças no código do Free My TV, prontas para aplicar no original |
| [`config.byintek.properties`](config.byintek.properties) | As configurações usadas no build: cidade, idioma, tema, endereço do feed |
| [`ytfeed/`](ytfeed/) | O serviço do feed do YouTube que roda na LXC: script, instalador e guia de login |

## O cenário

> **Os IPs, o número da LXC e o apelido SSH deste documento são exemplos.** Para usar na sua rede, troque o endereço do
> feed em dois lugares: `youtube_feed` no `config.properties` e o `<domain>` de
> `app/res/xml/network_security_config.xml` (no patch). O APK pronto busca o feed num IP fixo da minha rede, então
> para a fileira do YouTube funcionar na sua rede é preciso compilar de novo.

O U90 Max tem **duas placas** dentro da mesma caixa:

| IP | Placa | Papel |
|---|---|---|
| 192.168.1.20 | Android da Byintek | Liga primeiro e mostra o menu. Cuida de foco, keystone e HDMI. **Não foi alterada.** |
| 192.168.1.21 | Módulo Google TV: "4K Google TV Stick" da Skyworth (Amlogic, Android 14, 2 GB de RAM) | Onde o Free My TV foi instalado |

O módulo Google TV vinha com a tela inicial do Google, pesada e cheia de anúncios. Ela usava ~176 MB, num aparelho que
tinha só ~430 MB livres. Agora, quando escolho "Google TV" no menu da Byintek, abre direto o Free My TV.

```
Proxmox (192.168.0.2)
└── LXC 120 "youtube-feed" (192.168.0.10)
      ├── a cada 5 min: lê as inscrições → últimos vídeos (RSS) → tira Shorts, lives e vídeos > 2 h
      └── serve http://192.168.0.10:8080/feed.json
                │
                ▼  a cada 5 min
Projetor, módulo Google TV (192.168.1.21)
└── Free My TV: fileira de vídeos acima da prateleira → OK abre o vídeo no YouTube
```

## O que mudei no Free My TV

Todas as mudanças estão em [`free-my-tv-byintek.patch`](free-my-tv-byintek.patch), feito sobre o commit
[`fa47183`](https://github.com/simbasjungles/free-my-tv/commit/fa47183) do original.

| Mudança | Onde |
|---|---|
| Prateleira na minha ordem (YouTube, **Crunchyroll**, Prime Video, Globoplay, Netflix). O Crunchyroll não existia na lista. HBO Max, Disney+ e Paramount+ saíram da prateleira, mas continuam em "Todos os apps" | `HomeApps.java` (`SHELF`) |
| Pacotes de sistema da Skyworth/SDT do módulo Google TV protegidos: atalhos do controle, atualizações, LED e outros. O app nunca os desliga | `HomeMode.java` (`PROTECTED`) |
| **Contorno de destaque** no item selecionado: branco grosso com uma borda escura por fora, visível sobre qualquer fundo | `HomeView.java` (`drawRing`) |
| **Plano de fundo nítido**, em resolução cheia e quase sem escurecer. Antes ele ficava desfocado e escuro atrás do relógio | `Backdrop.java` |
| **Hora, data e clima menores**, no canto superior direito, abaixo dos botões, com sombra para ler sobre a foto | `HomeView.java` (`drawClock`) |
| **Fileira de vídeos do YouTube** acima da prateleira: até 30 vídeos, do mais novo ao mais antigo, com miniatura, título, canal e duração. OK abre o vídeo no app do YouTube | `Videos.java` (novo), `HomeView.java` (`drawVideos`), `Recs.java` |
| Nova opção `youtube_feed` no `config.properties`, e `latitude=auto` para tirar a cidade do fuso do projetor | `build.sh` |
| HTTP liberado **só** para o IP da LXC (192.168.0.10). Todo o resto continua só em HTTPS | `network_security_config.xml` (novo), `AndroidManifest.xml` |

Configurações do build ([`config.byintek.properties`](config.byintek.properties)): cidade pelo fuso do projetor (`latitude=auto`), região BR, português,
°C, tema sempre escuro, sem preços de criptomoedas e sem chave do TMDB. Sem essa chave, o app não mostra as sugestões
de filmes, e quem ocupa o lugar delas é a fileira do YouTube.

## Instalar o APK pronto

Primeiro, no Google TV do projetor: *Configurações → Sistema → Sobre*, aperte 7 vezes em *Build do SO do Android TV*.
Depois, em *Opções do desenvolvedor*, ative a **Depuração USB**. No PC, com o [adb](https://developer.android.com/tools/releases/platform-tools):

```bash
adb connect 192.168.1.21:5555
```

```bash
adb install -r apk/FreeMyTV-Byintek-U90Max.apk
```

Depois, no projetor: abra **Free My TV → Tela inicial → Free My TV** e aceite *Permitir depuração USB* (marque
*Sempre permitir*). Para desfazer tudo: **Free My TV → Tela inicial → Original**.

Detalhes que apareceram na instalação:

- **Play Protect:** o Google Play Protect barrou o APK (`INSTALL_FAILED_VERIFICATION_FAILURE`). Foi preciso desligar
  *Verificar apps com o Play Protect* no projetor durante a instalação.
- **Wi-Fi salvo pelo assistente:** o Wi-Fi tinha sido salvo pelo assistente de configuração inicial. Antes da troca, foi
  preciso esquecer a rede e conectar de novo em *Configurações → Rede e Internet*. Sem isso, o Android apagaria a rede
  ao desligar o assistente.
- **Assinatura:** este APK é assinado com a minha chave. Para instalar uma versão que você mesmo compilou, desinstale
  esta antes.

## Compilar a partir do código

```bash
git clone https://github.com/simbasjungles/free-my-tv
```

```bash
cd free-my-tv && git checkout fa47183 && git apply ../free-my-tv-byintek.patch
```

```bash
cp ../config.byintek.properties config.properties && ./build.sh
```

Precisa de JDK 17 ou mais novo e do Android SDK (`platforms;android-34`). No Windows com JDK 21, o `d8` do build-tools
34 falha com `NullPointerException` em `DreamView$1.class`. Instale o **build-tools 35.0.0**: o `build.sh` usa a versão
mais nova que encontrar. O primeiro build cria `freemytv.keystore`. **Guarde esse arquivo**, porque as atualizações
precisam da mesma assinatura. Ele fica fora do Git.

O plano de fundo vai para o projetor pela função *Minhas fotos* do app:

```bash
python3 tools/photos.py 192.168.1.21 minha-imagem.jpg
```

## O feed do YouTube (LXC)

O serviço está em [`ytfeed/`](ytfeed/): Python 3, só biblioteca padrão. O guia de login com a conta Google está em
[`ytfeed/COMO-CONECTAR.md`](ytfeed/COMO-CONECTAR.md).

- **LXC:** Proxmox 8.4, CT 120, Debian 12, 512 MB de RAM, 4 GB de disco, IP fixo 192.168.0.10, `onboot=1` (volta
  sozinha depois de uma queda de energia).
- **Login:** OAuth com o fluxo de dispositivo (código digitado no celular) e o escopo `youtube.readonly`. O app do
  Google Cloud precisa estar **publicado**. Em modo de teste, o Google bloqueia o login (`403 access_denied`) e
  expiraria o acesso a cada 7 dias.
- **Como monta a lista:** inscrições (relidas a cada 12 h) → RSS de cada canal (não gasta cota) → `videos.list` para a
  duração → tira lives, vídeos acima de 2 h e Shorts → os 30 mais novos.
  - Os Shorts são detectados de dois jeitos: pelo link `/shorts/` no RSS e, nos vídeos de até 3 minutos, por um
    `HEAD /shorts/<id>`, que só responde 200 para Short.
- **Cota:** cerca de 13 unidades por atualização. Atualizando a cada 5 minutos, dá uns 3.800 das 10.000 diárias.
- **Ajustes** em `/etc/ytfeed/config.json`: `max_items`, `order` (`recent` ou `score`), `per_channel`, `days`,
  `max_seconds`, `favorites`, `blocked`.

Instalar numa LXC nova (como root, na pasta `ytfeed`):

```bash
sh install.sh
```

## Segredos que não estão aqui

O `.gitignore` deixa de fora, de propósito: `freemytv.keystore` (a chave que assina o APK), `config.properties`,
`client_secret*.json` (a credencial OAuth do Google) e o `token.json` da LXC. A pasta `free-my-tv/` também fica fora: é
só o clone do projeto original, e as mudanças estão no patch.

## Créditos

- [Free My TV](https://github.com/simbasjungles/free-my-tv), licença MIT, por Free My TV contributors.
- Adaptação para o Byintek U90 Max e feed do YouTube feitos com [Claude Code](https://claude.com/claude-code).
