from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

db = SQLAlchemy()

#
#Tabela associativa (muitas-para-muitos) cobradores <-> regioes
#
regiao_cobrador = db.Table(
    "regiao_cobrador",
    db.Column("regiao_id", db.Integer, db.ForeignKey("regiao.id"), primary_key=True),
    db.Column("cobrador_id", db.Integer, db.ForeignKey("usuario.id"), primary_key=True))

# ==========================
# Usuário (Admin ou Cobrador)
# ==========================
class Usuario(db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    senha = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # "admin" ou "cobrador"

    clientes = db.relationship("Cliente", back_populates="cobrador", lazy=True)

    regiao_id = db.Column(db.Integer, db.ForeignKey("regiao.id"), nullable=True)

    regioes = db.relationship("Regiao", secondary="regiao_cobrador", back_populates="cobradores")

    def __repr__(self):
        return f"<Usuario: {self.usuario} ({self.tipo})>"


# ==========================
# Região
# ==========================
class Regiao(db.Model):
    __tablename__ = "regiao"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)

    cobradores = db.relationship("Usuario", secondary="regiao_cobrador", back_populates="regioes")
    clientes = db.relationship("Cliente", back_populates="regiao", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Regiao {self.nome}>"

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "cobradores": [{"id": c.id, "usuario": c.usuario} for c in self.cobradores]
    }


# ==========================
# Cliente
# ==========================
class Cliente(db.Model):
    __tablename__ = "cliente"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(30), nullable=True)
    endereco = db.Column(db.String(120), nullable=False)

    cobrador_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)

    regiao_id = db.Column(db.Integer, db.ForeignKey("regiao.id"), nullable=True)
    regiao = db.relationship("Regiao", back_populates="clientes", lazy=True)

    cobrador = db.relationship("Usuario", back_populates="clientes")

    emprestimos = db.relationship(
        "Emprestimo",
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Cliente {self.nome}>"

# ==========================
# Empréstimo
# ==========================
class Emprestimo(db.Model):
    __tablename__ = "emprestimo"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    porcentagem = db.Column(db.Float, nullable=False, default=0.0)
    frequencia = db.Column(db.String(20), nullable=False)
    data_emprestimo = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    valor_total = db.Column(db.Float, nullable=False)
    saldo = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="em_aberto")

    cliente = db.relationship("Cliente", back_populates="emprestimos")
    parcelas = db.relationship("Parcela", backref="emprestimo", cascade="all, delete-orphan")
    pagamentos = db.relationship("Pagamento", backref="emprestimo", cascade="all, delete-orphan")

    def __init__(self, cliente_id, valor, porcentagem, frequencia, data_emprestimo=None):
        self.cliente_id = cliente_id
        self.valor = float(valor)
        self.porcentagem = float(porcentagem)
        self.frequencia = frequencia
        self.data_emprestimo = data_emprestimo or datetime.utcnow().date()
        self.valor_total = round(self.valor * (1 + self.porcentagem / 100), 2)
        self.saldo = self.valor_total
        self.status = "em_aberto"

    def gerar_parcelas(self, qtd_parcelas=None):
        total_com_juros = self.valor_total

        if self.frequencia == "diaria":
            intervalo = timedelta(days=1)
            qtd_parcelas = int(qtd_parcelas) if qtd_parcelas else 20
        elif self.frequencia == "semanal":
            intervalo = timedelta(weeks=1)
            qtd_parcelas = 4
        else:
            intervalo = timedelta(days=30)
            qtd_parcelas = 1

        # valor base arredondado
        valor_parcela = round(total_com_juros / qtd_parcelas, 2)
        # ajuste final para que a soma das parcelas sejam igual ao total
        ultima_parcela = valor_parcela + round(total_com_juros - (valor_parcela * qtd_parcelas), 2)

        parcelas = []
        data_vencimento = self.data_emprestimo

        for i in range(qtd_parcelas):
            if self.frequencia == "diaria":
                while True:
                    data_vencimento += timedelta(days=1)
                    if data_vencimento.weekday() != 6:
                        break
            else:
                data_vencimento = self.data_emprestimo + (intervalo * (i + 1))
                if data_vencimento.weekday() == 6:
                    data_vencimento += timedelta(days=1)

            numero = f"{i+1}/{qtd_parcelas}"
            valor = valor_parcela if i < qtd_parcelas - 1 else ultima_parcela

            parcela = Parcela(
                emprestimo_id=self.id,
                numero_parcela=numero,
                valor=valor,
                data_vencimento=data_vencimento,
                status="pendente"
            )
            parcelas.append(parcela)

        return parcelas


    def aplicar_pagamentos(self, valor_pago):
        self.saldo = round(max(0.0, self.saldo - float(valor_pago)), 2)
        if self.saldo <= 0:
            self.status = "quitado"

    def __repr__(self):
        return f"<Emprestimo {self.id} cliente={self.cliente_id} saldo={self.saldo}>"

    @property
    def valor_pendente(self):
        return sum(p.valor for p in self.parcelas if p.status != "pago")

# ==========================
# Parcela
# ==========================
class Parcela(db.Model):
    __tablename__ = "parcela"

    id = db.Column(db.Integer, primary_key=True)
    emprestimo_id = db.Column(db.Integer, db.ForeignKey("emprestimo.id"), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    valor_pago = db.Column(db.Float, default=0.0)
    numero_parcela = db.Column(db.String(10), nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="pendente")

    def __repr__(self):
        return f"<Parcela {self.numero_parcela} valor={self.valor} Emprestimo={self.emprestimo_id} Status={self.status}>"

# ==========================
# Pagamento
# ==========================
class Pagamento(db.Model):
    __tablename__ = "pagamento"

    id = db.Column(db.Integer, primary_key=True)
    emprestimo_id = db.Column(db.Integer, db.ForeignKey("emprestimo.id"), nullable=False)
    parcela_id = db.Column(db.Integer, db.ForeignKey("parcela.id"), nullable=True)
    valor = db.Column(db.Float, nullable=False)
    data_pagamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Pagamento {self.id} emprestimo={self.emprestimo_id} valor={self.valor}>"
