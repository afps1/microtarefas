SISTEMA DE MICROTAREFAS HIPERLOCAIS (SHORT-MILE) — MICROTAREFAS

1. VISÃO GERAL

Plataforma para execução de microtarefas dentro de condomínios, conectando moradores (demanda) e parceiros (execução), com uso de WhatsApp como interface principal e webapps leves para operação.

Nome do produto: Microtarefas
Repositório: github.com/afps1/microtarefas
Deploy: https://microtarefas-production.up.railway.app

Objetivo:
Eliminar tarefas repetitivas e inconvenientes do dia a dia do morador com rapidez e simplicidade.

---

2. PRINCIPAIS CASOS DE USO

- Levar lixo
- Pegar encomenda na portaria
- Comprar no mercadinho

Características:
- tarefas curtas (até 10–15 min)
- raio limitado (dentro do condomínio)
- alta frequência (especialmente lixo)

---

3. NOMENCLATURA

- Executor da tarefa = PARCEIRO (nunca "runner" — evitar termos em inglês)
- Solicitante = morador
- Produto = Microtarefas

---

4. ARQUITETURA

4.1 Camadas

Morador:
- cadastro via web (admin cadastra, ou formulário público)
- uso exclusivamente via WhatsApp

Parceiro:
- cadastro via web (admin ou formulário)
- aprovação manual pelo admin do condomínio
- operação via webapp (dashboard com auto-refresh a cada 8s)
- NÃO recebe notificação por WhatsApp — usa polling no dashboard

Admin:
- dois níveis: Admin Geral (empresa) e Admin Condomínio (síndico)
- painel web desktop

Backend:
- orquestra pedidos
- identifica usuários por telefone
- envia mensagens WhatsApp ao morador
- controla estado das tarefas

---

4.2 Multi-condomínio

- cada usuário pertence a um condomínio
- parceiros só veem tarefas do seu condomínio
- serviços e preços configuráveis por condomínio (tabela service_types)

---

5. FLUXO OPERACIONAL

5.1 Morador (via WhatsApp)

1. envia mensagem: "quero levar o lixo"
2. GPT-4 mini interpreta intenção
3. bot responde com serviço + preço: "Você quer: Levar lixo — R$ 15,00. Confirma? Responda sim ou não."
4. morador confirma → tarefa criada (status: solicitado)
5. parceiro aceita → morador recebe: "✅ [Nome] aceitou sua tarefa e está a caminho!"
6. parceiro marca em execução → morador recebe notificação
7. parceiro marca concluído → morador recebe: valor + chave Pix do parceiro
8. parceiro marca recebido → morador recebe pedido de avaliação (1–5)
9. morador responde com número → avaliação registrada

---

5.2 Parceiro (via webapp)

1. acessa dashboard (login OTP por e-mail)
2. dashboard atualiza a cada 8s automaticamente
3. nova tarefa: alerta sonoro (beep 880Hz) + vibração (Android)
4. clica "Aceitar" → tarefa reservada para ele (transacional)
5. avança status: aceito → em_execucao → concluido → recebido

---

5.3 Pagamento

- Pix direto do morador para o parceiro (fora da plataforma)
- sistema envia chave Pix do parceiro ao morador quando tarefa é concluída
- empresa não intermedia financeiramente

---

6. STATUS DA TAREFA

solicitado → aceito → em_execucao → concluido → recebido

---

7. MODELO ECONÔMICO

- Fee mensal do condomínio para a empresa (B2B, MRR)
- Sem intermediação financeira de transações
- Futuro: assinatura parceiro, fee por condomínio

---

8. CADASTRO

8.1 Morador
- nome, telefone, apartamento, e-mail (opcional)
- cadastrado pelo admin do condomínio ou formulário público
- validação: OTP (mockado no MVP — apenas loga no console)

8.2 Parceiro
- nome, telefone, e-mail, chave Pix
- status: pending → approved (aprovação manual pelo admin)
- foto: campo existe no modelo, não obrigatório no MVP

---

9. ADMIN

9.1 Admin Geral
- cadastra e gerencia condomínios
- cadastra admins de condomínio

9.2 Admin Condomínio (síndico)
- visão geral (stats do dia)
- serviços e preços (CRUD completo, preço em centavos no DB)
- parceiros: aprovar, bloquear, editar, remover + nota média
- moradores: ativar/desativar, editar, remover
- tarefas: listagem com tipo, morador, parceiro, status, nota, data

---

10. TECNOLOGIA

Backend:
- FastAPI + Python 3.11
- MySQL (Railway plugin)
  - Variáveis: DB_HOST, DB_NAME, DB_USER, DB_PASS
- SQLAlchemy ORM

WhatsApp:
- API oficial da Meta
  - Variáveis: VERIFY_TOKEN, WHATSAPP_TOKEN, WHATSAPP_MSG_URL

IA / NLP:
- GPT-4 mini (OpenAI)
  - Variáveis: OPENAI_API_KEY, OPENAI_MODEL, OPENAI_API_URL
  - URL correta: https://api.openai.com/v1/chat/completions

Frontend parceiro:
- HTML + JavaScript responsivo (mobile-first)
- Autenticação JWT stateless via OTP por e-mail (mockado no MVP)
- Auto-refresh a cada 8s com alerta sonoro + vibração

Admin:
- HTML + JavaScript para desktop
- Autenticação: e-mail + senha (bcrypt + JWT)

Infra:
- GitHub: conta afps1
- Deploy: Railway (serviço microtarefas + plugin MySQL)
- Porta: 8080

Estrutura:
microtarefas/
├── backend/        ← FastAPI
├── frontend/       ← webapp do parceiro (/app)
└── admin/          ← painel admin (/admin)

---

11. MODELOS DE BANCO (principais)

- Condominium, Resident, Runner (= parceiro), AdminUser, Task
- ServiceType — serviços com preço por condomínio (price em centavos)
- PendingRequest — pedido aguardando confirmação do morador
- MagicLink — tokens para autenticação (parceiro)
- OtpCode — OTP de e-mail
- Rating — avaliação do parceiro (1–5) por tarefa

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

---

14. OBJETIVO FINAL

Criar uma infraestrutura de execução física hiperlocal escalável, iniciando em condomínios e expandindo para outros microterritórios.
