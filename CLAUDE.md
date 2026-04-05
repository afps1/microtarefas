SISTEMA DE MICROTAREFAS HIPERLOCAIS (SHORT-MILE) - DOCUMENTO CONSOLIDADO

1. VISÃO GERAL

Plataforma para execução de microtarefas dentro de condomínios, conectando moradores (demanda) e runners (execução), com uso de WhatsApp como interface principal e webapps leves para operação.

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

3. ARQUITETURA

3.1 Camadas

Morador:
- cadastro via web
- uso via WhatsApp

Runner:
- cadastro via web
- operação via WhatsApp + magic link + webapp

Admin:
- painel web multi-condomínio

Backend:
- orquestra pedidos
- identifica usuários por telefone
- envia mensagens WhatsApp
- controla estado das tarefas

---

3.2 Multi-condomínio

Sistema deve suportar múltiplos condomínios:

- cada usuário pertence a um condomínio
- runners só recebem tarefas do seu condomínio
- regras e preços são configuráveis por condomínio

---

4. FLUXO OPERACIONAL

4.1 Morador

1. envia mensagem no WhatsApp:
   "quero levar o lixo"
2. sistema interpreta intenção
3. confirma serviço e valor
4. busca runner
5. informa runner escolhido

---

4.2 Runner

1. recebe mensagem com magic link
2. clica no link
3. abre webapp já autenticado
4. vê tarefa
5. clica "Aceitar"
6. executa
7. marca "Concluído"
8. marca "Recebi"

---

4.3 Pagamento

- pagamento via Pix direto (fora da plataforma)
- fluxo padrão: pagar depois

---

5. MAGIC LINK E SEGURANÇA

Cada runner recebe link único contendo:

- task_id
- runner_id
- token/OTP único
- expiração curta

Regras:
- link individual
- expira rapidamente (3–10 min)
- não reserva tarefa automaticamente
- aceitação é transacional no backend

---

6. STATUS DA TAREFA

- solicitado
- aceito
- em execução
- concluído
- recebido

---

7. PORTARIA

Sem uso de app.

Validação por:
- nome do runner
- apartamento
- autorização verbal
- eventualmente código simples

---

8. PIX E PAGAMENTO

- QR Code Pix contém payload "copia e cola"
- runner pode escanear QR do mercadinho
- sistema extrai string e envia ao morador

Fluxo mercadinho:
1. runner escaneia QR
2. sistema envia código
3. morador paga
4. runner retira produto

---

9. CADASTRO

9.1 Morador

- nome
- telefone
- apartamento
- condomínio
- validação por OTP

---

9.2 Runner

- nome completo
- telefone validado
- foto
- chave Pix
- status (pendente/aprovado)

Aprovação manual obrigatória

---

10. ADMIN

- gerenciamento de condomínios
- aprovação de runners
- gestão de moradores
- visualização de pedidos
- configuração de preços

---

11. MODELO ECONÔMICO

Inicial:
- sem intermediação financeira

Futuro:
- assinatura runner
- fee condomínio

---

12. TECNOLOGIA

Backend:
- FastAPI
- PostgreSQL

Frontend:
- WebApp (PWA)

WhatsApp:
- API oficial

QR Code:
- leitura via JS ou Android

---

13. PRINCÍPIOS DO SISTEMA

- simplicidade máxima
- baixa fricção
- rapidez
- confiança local
- não depender de infraestrutura do condomínio

---

14. INSIGHT CENTRAL

O valor não está no app.

Está em:
- proximidade
- recorrência
- execução rápida

---

15. OBJETIVO FINAL

Criar uma infraestrutura de execução física hiperlocal escalável, iniciando em condomínios e expandindo para outros microterritórios.
