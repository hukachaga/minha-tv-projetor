# Ligar o feed do YouTube à sua conta

Os exemplos usam a LXC **120** com IP 192.168.0.10 e o apelido SSH `proxmox` para o host: troque pelos seus.

O serviço roda na LXC **120 `youtube-feed`** (192.168.0.10) do Proxmox. Ele lê as suas inscrições, descarta Shorts e
lives, dá prioridade aos canais de que você mais curte vídeos e publica `http://192.168.0.10:8080/feed.json`, que o
Free My TV mostra acima da prateleira.

## 1. Criar o acesso no Google Cloud (uma vez, ~10 min)

1. Abra <https://console.cloud.google.com/> e crie um projeto (ex.: `ytfeed`).
2. **APIs e serviços → Biblioteca** → ative **YouTube Data API v3**.
3. **APIs e serviços → Tela de consentimento OAuth** (ou "Google Auth Platform"):
   - Tipo **Externo**, nome do app `ytfeed`, seu e-mail como suporte e contato.
   - Em **Público-alvo**, clique em **Publicar app** (status *Em produção*). Em modo *Teste*, o Google expira o login a
     cada 7 dias. Não precisa enviar para verificação: no login aparece um aviso "app não verificado", e você segue
     em *Avançado → Acessar ytfeed*.
4. **Credenciais → Criar credenciais → ID do cliente OAuth** → tipo **TVs e dispositivos de entrada limitada** →
   **Fazer download do JSON**.
5. Renomeie o arquivo para `client_secret.json`.

## 2. Copiar o arquivo para a LXC e entrar

No terminal deste PC, na pasta onde está o `client_secret.json`:

```bash
scp client_secret.json proxmox:/tmp/
```

```bash
ssh -t proxmox "pct push 120 /tmp/client_secret.json /etc/ytfeed/client_secret.json --perms 600 && rm /tmp/client_secret.json && pct exec 120 -- /opt/ytfeed/ytfeed.py auth"
```

O comando mostra um endereço (google.com/device) e um código. Abra no celular, digite o código, entre com a conta
do YouTube e permita. Quando aparecer *Signed in*, gere o feed:

```bash
ssh proxmox "pct exec 120 -- /opt/ytfeed/ytfeed.py refresh"
```

Depois disso ele se atualiza sozinho a cada 5 minutos, e o projetor busca a lista a cada 5.

## Ajustes

`/etc/ytfeed/config.json` na LXC:

| Chave | O que faz | Padrão |
|---|---|---|
| `days` | Só vídeos dos últimos N dias | 10 |
| `max_items` | Quantos vídeos no feed (o projetor mostra até 30) | 30 |
| `per_channel` | No máximo N vídeos por canal; `0` sem limite | 0 |
| `order` | `recent`: do mais novo ao mais antigo; `score`: canais que você mais curte primeiro | `recent` |
| `max_seconds` | Deixa de fora vídeos mais longos que isso (gravações de live); `0` mantém todos | 7200 (2 h) |
| `favorites` | Canais (nome ou id) que sobem na lista | `[]` |
| `blocked` | Canais (nome ou id) que nunca aparecem | `[]` |

Ver o que a última atualização encontrou: `ssh proxmox "pct exec 120 -- /opt/ytfeed/ytfeed.py status"`.
