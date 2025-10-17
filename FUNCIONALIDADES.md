# Funcionalidades Implementadas

## ✅ Sistema Completo de Controle de Empréstimos

### 1. **Filtro Automático por Cobrador**
- O dashboard do cobrador exibe **apenas clientes das regiões que ele gerencia**
- Implementado automaticamente ao fazer login
- Não é necessário selecionar filtros manualmente

### 2. **Filtro de Data no Dashboard do Cobrador**
- Campo de data para visualizar cobranças de qualquer dia específico
- Padrão: mostra cobranças do dia atual
- Mantém a data selecionada após atualizar a página

### 3. **Gestão Completa de Pagamentos**

#### 📥 **Receber Pagamento**
- **Pagamento Completo**: Marca parcela como "pago" quando valor >= valor restante
- **Pagamento Parcial**: 
  - Acumula valor em `valor_pago`
  - Marca parcela como "parcialmente_paga"
  - Calcula e exibe valor restante automaticamente
- Registra todos os pagamentos no histórico

#### ✏️ **Editar Pagamento**
- Permite alterar o valor de um pagamento já registrado
- Recalcula automaticamente:
  - Total pago da parcela
  - Status da parcela (pendente/parcial/pago)
  - Valor restante

#### ❌ **Cancelar Pagamento**
- Devolve o valor do pagamento para a parcela
- Atualiza status da parcela automaticamente:
  - Se valor_pago = 0: volta para "pendente"
  - Se 0 < valor_pago < valor: fica "parcialmente_paga"
- Remove o registro de pagamento do histórico

### 4. **Dashboards Específicos**

#### 👨‍💼 **Dashboard Admin**
- Visão completa de todos os clientes e empréstimos
- Filtros por região e cobrador
- Totais: recebido, a receber e atrasado
- Gestão completa de parcelas e pagamentos

#### 👤 **Dashboard Cobrador**
- Mostra apenas clientes das suas regiões
- Filtro de data para cobranças específicas
- Resumo por cliente com:
  - Total pendente
  - Total atrasado
  - Histórico de parcelas
- Interface simplificada para registro de pagamentos

## 🔐 Credenciais de Acesso

**Admin:**
- Usuário: `admin`
- Senha: `123`

## 📊 Status de Parcelas

1. **Pendente** (amarelo): Parcela não paga
2. **Parcialmente Paga** (azul): Parte do valor já foi pago
3. **Pago** (verde): Parcela quitada completamente
4. **Atrasado** (vermelho): Parcela vencida e não paga

## 🎯 Fluxo de Trabalho

1. **Admin cadastra:**
   - Regiões
   - Cobradores (vinculados às regiões)
   - Clientes (vinculados a região e cobrador)
   - Empréstimos

2. **Cobrador acessa:**
   - Vê apenas seus clientes (filtro automático)
   - Seleciona data de cobrança
   - Registra pagamentos (completos ou parciais)
   - Pode editar ou cancelar pagamentos se necessário

## ⚠️ Observações Importantes

- Parcelas com vencimento em **domingo** são movidas automaticamente para **segunda-feira**
- Empréstimos diários **não geram parcelas aos domingos**
- Sistema calcula juros e divide em parcelas automaticamente
- Suporte completo para pagamento parcial com rastreamento de valor restante
