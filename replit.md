# Sistema de Controle de Empréstimos

## Visão Geral
Sistema completo de gestão de empréstimos desenvolvido com Flask, Bootstrap e SQLite. Permite controle de clientes, regiões, cobradores e empréstimos com funcionalidades avançadas de gestão de pagamentos.

## Tecnologias Utilizadas
- **Backend**: Python 3.11 com Flask
- **ORM**: SQLAlchemy com Flask-SQLAlchemy
- **Frontend**: Bootstrap 5 + JavaScript
- **Banco de Dados**: SQLite

## Estrutura do Projeto
```
.
├── app.py                 # Aplicação principal Flask com todas as rotas
├── models.py              # Modelos do banco de dados
├── templates/             # Templates HTML
│   ├── base.html
│   ├── login.html
│   ├── dashboard_admin.html
│   ├── dashboard_cobrador.html
│   ├── cadastro_cliente.html
│   ├── adicionar_emprestimo.html
│   ├── cadastrar_regiao.html
│   ├── cadastrar_cobrador.html
│   ├── regioes.html
│   └── listar_cobradores.html
├── static/                # Arquivos estáticos (CSS, JS)
└── sistema.db            # Banco de dados SQLite (gerado automaticamente)
```

## Funcionalidades Principais

### Para Administradores
- Dashboard administrativo com visão geral de empréstimos
- Filtros por região e cobrador
- Cadastro de clientes, regiões e cobradores
- Criação de empréstimos com cálculo automático de parcelas e juros
- Gestão completa de pagamentos (parcial, completo, edição, cancelamento)
- Visualização de totais: recebido, a receber e atrasado

### Para Cobradores
- Dashboard personalizado mostrando apenas clientes das regiões gerenciadas
- Filtro de data para visualizar cobranças de dias específicos
- Visualização de parcelas do dia com valores a receber
- Registro de pagamentos completos e parciais
- Controle de status de parcelas (pago, parcialmente paga, pendente, atrasado)
- Resumo por cliente com totais pendentes e atrasados

## Modelos do Banco de Dados

### Usuario
- Tipos: admin ou cobrador
- Relacionamento muitos-para-muitos com Regiões
- Um cobrador pode gerenciar múltiplas regiões

### Regiao
- Nome da região
- Relacionamento com múltiplos cobradores e clientes

### Cliente
- Dados pessoais (nome, telefone, endereço)
- Vinculado a uma região e um cobrador responsável
- Relacionamento com empréstimos

### Emprestimo
- Valor, porcentagem de juros, frequência (diária, semanal, mensal)
- Cálculo automático do valor total com juros
- Geração automática de parcelas
- Status: em_aberto ou quitado

### Parcela
- Valor da parcela e valor já pago
- Data de vencimento
- Status: pendente, parcialmente_paga, pago
- Sistema de pagamento parcial com controle de valor restante

### Pagamento
- Registro histórico de todos os pagamentos
- Vinculado a empréstimo e parcela
- Data e valor do pagamento

## Funcionalidades Implementadas Recentemente (Out 2025)

### 1. Filtro Automático por Cobrador
- Dashboard do cobrador exibe apenas clientes das regiões que ele gerencia
- Implementado no `dashboard_cobrador()` usando `session['usuario_id']`
- Filtragem automática de parcelas e clientes por `regioes_ids`

### 2. Filtro de Data
- Campo de data no dashboard do cobrador
- Permite visualizar cobranças de qualquer dia específico
- Mantém a data selecionada após submissão do formulário

### 3. Gestão Avançada de Pagamentos

#### Pagamento Completo
- Rota: `/receber_pagamento/<parcela_id>`
- Marca parcela como "pago" quando valor >= valor restante
- Registra pagamento na tabela de histórico

#### Pagamento Parcial
- Mesma rota suporta pagamento parcial
- Status alterado para "parcialmente_paga"
- Valor pago acumulado em `parcela.valor_pago`
- Valor restante calculado dinamicamente: `parcela.valor - parcela.valor_pago`

#### Editar Pagamento
- Rota: `/editar_pagamento/<pagamento_id>`
- Permite alterar apenas o valor de um pagamento já registrado
- Recalcula automaticamente o `valor_pago` da parcela
- Atualiza status conforme novo total

#### Cancelar Pagamento
- Rota: `/cancelar_pagamento/<pagamento_id>`
- Devolve o valor para a parcela (subtrai de `valor_pago`)
- Remove o registro de pagamento
- Atualiza status da parcela (pendente ou parcialmente_paga)

## Credenciais Padrão
- **Usuário**: admin
- **Senha**: 123

## Como Usar

1. Faça login com as credenciais de admin
2. Cadastre regiões
3. Cadastre cobradores e vincule às regiões
4. Cadastre clientes e associe a região e cobrador
5. Crie empréstimos para os clientes
6. Cobradores fazem login e gerenciam pagamentos de suas regiões

## Variáveis de Ambiente
- `SESSION_SECRET`: Chave secreta para sessões Flask (já configurada)

## Observações
- Parcelas com vencimento em domingo são automaticamente movidas para segunda-feira
- Empréstimos diários não geram parcelas aos domingos
- Sistema calcula automaticamente juros e divide em parcelas
- Suporte completo para pagamento parcial com rastreamento de valor restante
