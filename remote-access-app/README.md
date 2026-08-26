# Remote Access App — MVP

Protótipo funcional de um app de acesso remoto no estilo AnyDesk/TeamViewer:
ID de máquina, pedido de conexão, aceitar/recusar, e controle total (tela +
mouse + teclado) via navegador.

## Estrutura

```
remote-access-app/
├── signaling-server/     # Node.js — "apresenta" técnico e cliente pelo ID
├── technician-panel/     # Página web que você (técnico) usa para conectar
└── client-agent/         # Script Python que roda no PC do cliente
```

## Como rodar (ambiente de testes)

### 1. Servidor de sinalização
```bash
cd signaling-server
npm install
npm start
# Servidor rodando em ws://localhost:8080
```

### 2. Painel do técnico
Abra `technician-panel/index.html` direto no navegador (duplo clique já
funciona, ou sirva com `python -m http.server` na pasta).

### 3. Agente do cliente
```bash
cd client-agent
pip install -r requirements.txt
python agent.py
```
Ao rodar, o terminal mostra o **ID de 9 dígitos** da máquina — é esse número
que o cliente te passa por telefone/WhatsApp.

### 4. Testando
1. Rode o agente no computador "cliente" (pode ser o mesmo PC pra testar).
2. Copie o ID mostrado no terminal.
3. Abra o painel do técnico, cole o ID, clique em Conectar.
4. No PC do cliente vai aparecer o popup de Aceitar/Recusar.
5. Aceitando, a tela aparece no painel do técnico e você já pode mover o
   mouse e digitar sobre o vídeo.

> **Importante:** para conectar duas máquinas em **redes diferentes** (o
> caso real de suporte técnico), o servidor de sinalização precisa estar
> hospedado num endereço público (VPS), e trocar `ws://localhost:8080` por
> `wss://seu-dominio.com` nos dois arquivos (`agent.py` e `index.html`).
> Em muitas redes (principalmente 4G/redes corporativas) também vai ser
> necessário um **servidor TURN** — veja a seção abaixo.

## O que esse MVP já faz
- Gera e memoriza um ID fixo por máquina
- Fluxo de pedido → aceitar/recusar, com popup nativo no Windows
- Transmissão de tela em tempo real (WebRTC)
- Controle de mouse (mover, clicar, scroll) e teclado
- Conexão criptografada (padrão do WebRTC, DTLS/SRTP)

## O que falta para virar uma ferramenta "de verdade" no seu dia a dia

| Item | Por quê importa | Esforço |
|---|---|---|
| **Empacotar o agente em `.exe`** | Cliente não pode precisar instalar Python | Médio (PyInstaller) |
| **Servidor TURN** | Sem isso, conexões em redes 4G/corporativas com NAT restritivo (comum) falham | Baixo (serviço pago barato ou self-host com coturn) |
| **HTTPS/WSS + domínio próprio** | Necessário pra rodar fora da rede local, e navegadores exigem HTTPS para APIs de mídia em produção | Baixo-médio |
| **Autenticação/senha de sessão** | Hoje qualquer um que souber o ID pode *pedir* acesso (o cliente ainda precisa aceitar, mas reforça segurança) | Baixo |
| **Transferência de arquivos** | Você mencionou copiar/enviar arquivos — não incluído neste MVP | Médio (canal de dados extra + chunking) |
| **Rodar como serviço do Windows** | Permite acessar o PC mesmo sem o cliente estar logado/com sessão ativa (acesso "não assistido") | Médio-alto |
| **Log de sessões / auditoria** | Rastro de quando e o que foi acessado — importante profissionalmente | Baixo |
| **Reconexão automática e qualidade adaptativa** | AnyDesk/TeamViewer ajustam qualidade de vídeo conforme a rede | Médio |

## Aviso de segurança
Como essa ferramenta dá controle total sobre computadores de terceiros, ela
deve sempre:
- Exigir consentimento explícito antes de cada sessão (já implementado)
- Nunca ser distribuída/usada sem o conhecimento do dono da máquina
- Ter os dados de conexão (ID, logs) protegidos — não exponha o servidor de
  sinalização sem HTTPS/WSS em produção
