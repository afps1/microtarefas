SISTEMA DE MICROTAREFAS HIPERLOCAIS (SHORT-MILE) — POSTINO

1. VISÃO GERAL

Plataforma para execução de microtarefas dentro de condomínios e outros microterritórios, conectando solicitantes (demanda) e parceiros (execução), com uso de WhatsApp como interface principal e webapps leves para operação.

Nome do produto: Postino
Repositório: github.com/afps1/microtarefas
Deploy: https://postino.com.br (Railway, domínio via Hostinger)
URL Railway direta: https://microtarefas-production.up.railway.app

Empresa criadora: Afeltec (Andre — andre@afeltec.com.br)

Objetivo:
Eliminar tarefas repetitivas e inconvenientes do dia a dia com rapidez e simplicidade.

---

2. PRINCIPAIS CASOS DE USO

- Pegar entrega na portaria
- Buscar encomenda
- Comprar no mercadinho

Características:
- tarefas curtas (até 10–15 min)
- raio limitado (dentro do condomínio/local)
- alta frequência

---

3. NOMENCLATURA

- Executor da tarefa = PARCEIRO (nunca "runner" — evitar termos em inglês)
- Solicitante = quem pede a tarefa (nunca "morador" nas interfaces — termo genérico)
- Unidade/Local = campo de localização (nunca "Ap." ou "apartamento" — termo genérico)
- Cliente = condomínio ou local contratante (nas interfaces admin — nunca "condomínio")
- Produto = Postino

---

4. ARQUITETURA

4.1 Camadas

Solicitante:
- cadastro via web (admin cadastra, ou formulário público)
- uso exclusivamente via WhatsApp

Parceiro:
- cadastro via web (admin ou formulário)
- aprovação manual pelo admin do condomínio
- operação via webapp PWA (dashboard com auto-refresh a cada 8s)
- recebe Web Push Notification (VAPID, sem Firebase)

Admin:
- dois níveis: Admin Geral (empresa) e Admin Condomínio (síndico/gestor)
- painel web desktop

Backend:
- orquestra pedidos
- identifica usuários por telefone
- envia mensagens WhatsApp ao solicitante
- controla estado das tarefas

---

4.2 Multi-condomínio

- cada usuário pertence a um condomínio/local
- parceiros só veem tarefas do seu condomínio
- serviços e preços configuráveis por condomínio (tabela service_types)

---

5. FLUXO OPERACIONAL

5.1 Solicitante (via WhatsApp)

1. envia mensagem: "quero pegar uma entrega"
2. GPT-4 mini interpreta intenção com lista de serviços do condomínio
3. bot responde com serviço + preço: "Você quer: Pegar entrega na portaria — R$ 15,00. Confirma? Responda sim ou não."
4. solicitante confirma → tarefa criada (status: solicitado)
5. parceiro aceita → solicitante recebe notificação + foto do parceiro
6. parceiro marca em execução → solicitante recebe notificação
7. parceiro marca concluído → solicitante recebe: valor + chave Pix do parceiro (2 mensagens separadas)
8. parceiro marca recebido → solicitante recebe pedido de avaliação (1–5)
9. solicitante responde com número → avaliação registrada

---

5.2 Parceiro (via webapp PWA)

1. acessa dashboard (login OTP por e-mail)
2. dashboard atualiza a cada 8s automaticamente
3. nova tarefa: Web Push + alerta sonoro (AudioContext, desbloqueado no primeiro toque) + vibração (Android)
4. clica "Aceitar" → tarefa reservada (transacional, um parceiro de cada vez)
5. avança status: aceito → em_execucao → concluido → recebido
6. parceiro dedicado a uma tarefa por vez até concluir ou cancelar

---

5.3 Pagamento

- Pix direto do solicitante para o parceiro (fora da plataforma)
- sistema envia chave Pix em 2 mensagens separadas (valor + chave) para facilitar cópia
- empresa não intermedia financeiramente

---

6. STATUS DA TAREFA

solicitado → aceito → em_execucao → concluido → recebido
                                               ↘ cancelado

---

7. MODELO ECONÔMICO

- Fee mensal do condomínio/local para a empresa (B2B, MRR)
- Sem intermediação financeira de transações
- Mercados-alvo: condomínios, hospitais, centros comerciais, universidades
- Futuro: assinatura parceiro, fee por condomínio

---

8. CADASTRO

8.1 Solicitante
- nome, telefone, unidade/local, e-mail (opcional)
- cadastrado pelo admin do condomínio ou formulário público
- validação: OTP (mockado no MVP — apenas loga no console)

8.2 Parceiro
- nome, telefone, e-mail, chave Pix
- foto: cadastrada pelo admin do condomínio (Railway Volume /data/fotos/<runner_id>.jpg)
- status: pending → approved (aprovação manual pelo admin)

---

9. ADMIN

9.1 Admin Geral
- cadastra e gerencia clientes (condomínios)
- cadastra admins de condomínio

9.2 Admin Condomínio (síndico/gestor)
- sidebar com nome do cliente em destaque
- visão geral (stats do dia)
- serviços e preços (CRUD completo, preço em centavos no DB)
- parceiros: aprovar, bloquear, editar, remover + nota média + upload de foto
- solicitantes: ativar/desativar, editar, remover (campo Unidade/Local)
- tarefas: listagem com tipo, solicitante, parceiro, status, nota, data

---

10. TECNOLOGIA

Backend:
- FastAPI + Python 3.11
- MySQL (Railway plugin)
  - Variáveis: DB_HOST, DB_NAME, DB_USER, DB_PASS
- SQLAlchemy ORM
- Porta: 8080

WhatsApp:
- API oficial da Meta
  - Variáveis: VERIFY_TOKEN, WHATSAPP_TOKEN, WHATSAPP_MSG_URL, WHATSAPP_NUMBER
  - WHATSAPP_NUMBER exposto via GET /config (usado na landing page)

IA / NLP:
- GPT-4 mini (OpenAI)
  - Variáveis: OPENAI_API_KEY, OPENAI_MODEL, OPENAI_API_URL
  - URL correta: https://api.openai.com/v1/chat/completions
  - Intents: solicitar_tarefa, cancelar, status, listar_servicos, outro

Web Push:
- VAPID (sem Firebase), pywebpush 1.14.1
  - Variáveis: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY (base64url DER, linha única)
  - PushSubscription model no banco, re-subscription forçada a cada abertura

Contato admin (WhatsApp bot):
- CONTACT_EMAIL — e-mail exibido para números não cadastrados

Frontend parceiro (PWA):
- HTML + JavaScript responsivo (mobile-first)
- Autenticação JWT via OTP por e-mail (mockado no MVP)
- Auto-refresh 8s, Web Push, Badging API
- Ícones PNG azul 192/512px com iniciais "Pt"
- Todos SVGs nativos (sem emojis)
- URLs de API relativas (const API = "")
- Header em 2 linhas: linha 1 = Postino (esq) + Sair (dir); linha 2 = nome + nota (esq) + toggle disponível (dir)
- Toggle Disponível (verde) / Indisponível (vermelho) — persiste no banco via PATCH /tasks/me/available
- Runner.available (boolean, default true) — parceiros indisponíveis não recebem push nem aparecem no filtro

Landing page:
- landing/index.html servida em GET / via FileResponse
- Seções: hero, features, cards síndico/parceiro, WhatsApp CTA, microterritórios, como funciona
- Header com botões "Sou parceiro" e "Área admin" (texto + SVG no desktop, só SVG no mobile ≤480px)
- JS busca /config para exibir número WhatsApp e montar link wa.me

Admin:
- HTML + JavaScript para desktop
- Autenticação: e-mail + senha (bcrypt + JWT)
- URLs de API relativas

Infra:
- GitHub: conta afps1, repo microtarefas
- Deploy: Railway (auto-deploy on push to main)
- Domínio: postino.com.br (Hostinger — ALIAS @ → Railway, TXT _railway-verify)
- Railway Volume: /data (fotos dos parceiros)

Estrutura:
microtarefas/
├── backend/        ← FastAPI
├── frontend/       ← webapp do parceiro (/app)
├── admin/          ← painel admin (/admin)
└── landing/        ← landing page (/)

---

11. MODELOS DE BANCO (principais)

- Condominium, Resident, Runner (= parceiro), AdminUser, Task
- ServiceType — serviços com preço por condomínio (price em centavos)
- PendingRequest — pedido aguardando confirmação + awaiting_observation
- MagicLink — tokens para autenticação (parceiro)
- OtpCode — OTP de e-mail
- Rating — avaliação do parceiro (1–5) por tarefa
- TaskMessage — chat (sender: parceiro/morador, type: text/image)
- PushSubscription — subscription Web Push por parceiro

Normalização de telefone:
- DB armazena sem o 55 (ex: 11994840515)
- Meta envia com 55 (ex: 5511994840515)
- wa_phone() adiciona "55" na hora de enviar
- webhook strip "55" na hora de receber

---

12. ENDPOINTS TEMPORÁRIOS

POST /migrate/run?key=vemaqui123 — executa DDL de migração
POST /migrate/clean-tasks?key=vemaqui123 — limpa tarefas/ratings
POST /setup/admin?key={SETUP_KEY} — cria primeiro admin geral

---

13. PRINCÍPIOS DO SISTEMA

- simplicidade máxima
- baixa fricção
- rapidez
- confiança local
- não depender de infraestrutura do condomínio
- sem emojis nas interfaces (usar SVG)
- terminologia genérica (solicitante, unidade/local, cliente) para suportar múltiplos verticais

---

14. OBJETIVO FINAL

Criar uma infraestrutura de execução física hiperlocal escalável, iniciando em condomínios e expandindo para hospitais, centros comerciais, universidades e qualquer microterritório com alta circulação de pessoas.
