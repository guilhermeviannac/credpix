from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from models import db, Cliente, Usuario, Emprestimo, Pagamento, Parcela, Regiao
from datetime import datetime, timedelta, date
import os

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SESSION_SECRET', 'uma_chave_secreta_aqui')

db.init_app(app)

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(usuario="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado -> login: admin | senha: 123")


@app.template_filter("moeda")
def moeda(valor):
    if valor is None:
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario").strip()
        senha = request.form.get("senha").strip()

        user = Usuario.query.filter_by(usuario=usuario, senha=senha).first()

        if user and user.senha:
            session["usuario"] = user.usuario
            session["tipo"] = user.tipo
            session["usuario_id"] = user.id

            if user.tipo.lower() == "admin":
                flash(f"Bem vindo, {user.usuario.upper()}!", "success")
                return redirect(url_for("dashboard_admin"))
            elif user.tipo.lower() == "cobrador":
                flash(f"Bem vindo, {user.usuario.upper()}!", "success")
                return redirect(url_for("dashboard_cobrador"))
            else:
                flash(f"Bem vindo, {user.usuario.upper()}!", "success")
                return redirect(url_for("dashboard_admin"))
        else:
            flash("Usuário ou senha incorretos!", "danger")
            return render_template("login.html")

    return render_template("login.html")


@app.route("/adicionar_emprestimo", methods=["GET", "POST"])
def adicionar_emprestimo():
    clientes = Cliente.query.all()

    if request.method == "POST":
        try:
            cliente_id = int(request.form.get("cliente_id"))
            valor = float(request.form.get("valor"))
            porcentagem = float(request.form.get("porcentagem"))
            frequencia = request.form.get("frequencia")
            data_str = request.form.get("data_emprestimo")
            data_emprestimo = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else datetime.utcnow().date()
            qtd_parcelas = request.form.get("qtd_parcelas")

            #cria o emprestimo
            emprestimo = Emprestimo(
                cliente_id=int(cliente_id),
                valor=valor,
                porcentagem=porcentagem,
                frequencia=frequencia,
                data_emprestimo=data_emprestimo
            )

            db.session.add(emprestimo)
            db.session.commit()

            #gera parcelas automáticas
            parcelas = emprestimo.gerar_parcelas(qtd_parcelas)

            if parcelas:
                for parcela in parcelas:
                    parcela.emprestimo_id = emprestimo.id
                    db.session.add(parcela)
                db.session.commit()

            cliente = Cliente.query.get(cliente_id)
            flash(f"Empréstimo de (R$ {valor:.2f} - {frequencia}) registrado para {cliente.nome}!", "success")
            return redirect(url_for("dashboard_admin"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao registrar empréstimo: {e}", "danger")
            return redirect(url_for("adicionar_emprestimo"))

    return render_template("adicionar_emprestimo.html", clientes=clientes)


@app.route("/cadastrar_regiao", methods=["GET", "POST"])
def cadastrar_regiao():
    if request.method == "POST":
        nome = request.form["nome"]
        cobradores_ids = request.form.getlist("cobradores")

        if not nome:
            flash("Nome da região é obrigatório!", "danger")
            return redirect(url_for("cadastrar_regiao"))

        regiao = Regiao(nome=nome)

        if cobradores_ids:
            cobradores = Usuario.query.filter(Usuario.id.in_(cobradores_ids), Usuario.tipo=="cobrador").all()
            regiao.cobradores.extend(cobradores)

        db.session.add(regiao)
        db.session.commit()
        flash("Região cadastrada com sucesso!", "success")
        return redirect(url_for("cadastrar_regiao"))

    cobradores = Usuario.query.filter_by(tipo="cobrador").all()
    return render_template("cadastrar_regiao.html", cobradores=cobradores)


@app.route("/regioes")
def listar_regioes():
    regioes = Regiao.query.all()
    return render_template("regioes.html", regioes=regioes)


@app.route("/dashboard_admin")
def dashboard_admin():
    if "usuario" not in session or session["tipo"] != "admin":
        flash("Acesso Negado!", "danger")
        return redirect(url_for("login"))

    db.session.expire_all()

    regiao_id = request.args.get("regiao_id", type=int)
    cobrador_id = request.args.get("cobrador_id", type=int)

    page = request.args.get("page", 1, type=int)
    per_page = 3

    regioes = Regiao.query.all()
    cobradores = Usuario.query.filter_by(tipo="cobrador").all()

    clientes_query = Cliente.query.order_by(Cliente.nome.asc())

    if regiao_id:
        cobradores = Usuario.query.filter_by(regiao_id=regiao_id).all()
        clientes_query = clientes_query.filter_by(regiao_id=regiao_id)

    if cobrador_id:
        clientes_query = clientes_query.filter_by(cobrador_id=cobrador_id)

    clientes = clientes_query.paginate(page=page, per_page=per_page)

    total_recebido = 0
    total_a_receber = 0
    total_atrasado = 0
    now = datetime.now().date()

    todos_emprestimos = []

    for cliente in clientes:
        for emprestimo in cliente.emprestimos:
            todos_emprestimos.append(emprestimo)

            valor_pago_emprestimo = sum([p.valor_pago for p in emprestimo.parcelas if p.status in ["pago", "parcialmente_paga"]])
            valor_pendente_emprestimo = sum([p.valor - p.valor_pago for p in emprestimo.parcelas if p.status != "pago"])

            total_recebido += valor_pago_emprestimo
            total_a_receber += valor_pendente_emprestimo

            total_atrasado += sum([p.valor - p.valor_pago for p in emprestimo.parcelas if p.status != "pago" and p.data_vencimento < now])

            emprestimo.total_pago = valor_pago_emprestimo
            emprestimo.total_pendente = valor_pendente_emprestimo

    return render_template(
        "dashboard_admin.html",
        clientes=clientes.items,
        pagination=clientes,
        regiao_selecionada=regiao_id,
        cobrador_selecionado=cobrador_id,
        regioes=regioes,
        cobradores=cobradores,
        todos_emprestimos=todos_emprestimos,
        total_a_receber=total_a_receber,
        total_recebido=total_recebido,
        total_atrasado=total_atrasado,
        now=now
    )


@app.route("/dashboard_cobrador")
def dashboard_cobrador():
    if "usuario" not in session:
        flash("Faça login para continuar!", "danger")
        return redirect(url_for("login"))

    usuario_id = session.get("usuario_id")
    usuario = Usuario.query.get(usuario_id)
    now = datetime.now().date()

    if not usuario or usuario.tipo not in ["cobrador", "admin"]:
        flash("Acesso negado!", "danger")
        return redirect(url_for("login"))

    # --- Filtros da URL ---
    data_filtro = request.args.get("data_filtro")
    regiao_id_filtro = request.args.get("regiao_id", type=int)
    cobrador_id_filtro = request.args.get("cobrador_id", type=int)

    # --- Data ---
    if data_filtro:
        try:
            hoje = datetime.strptime(data_filtro, "%Y-%m-%d").date()
        except:
            hoje = date.today()
    else:
        hoje = date.today()

    # --- Caso seja cobrador ---
    if usuario.tipo == "cobrador":
        regioes_ids = [r.id for r in usuario.regioes]
    else:
        # Admin pode ver tudo (ou filtrar)
        if regiao_id_filtro:
            regioes_ids = [regiao_id_filtro]
        else:
            regioes_ids = [r.id for r in Regiao.query.all()]

    # --- Nenhuma região ---
    if not regioes_ids:
        flash("Nenhuma região encontrada!", "warning")
        return render_template(
            "dashboard_cobrador.html",
            dashboard=[],
            parcelas_hoje=[],
            total_a_receber=0,
            total_pago_hoje=0,
            total_nao_recebido=0,
            totais_pendentes={},
            totais_atrasados={},
            hoje=hoje.strftime("%d/%m/%Y"),
            data_filtro_value=hoje.strftime("%Y-%m-%d"),
            regioes=Regiao.query.all(),
            cobradores=Usuario.query.filter_by(tipo="cobrador").all(),
            regiao_id_filtro=regiao_id_filtro,
            cobrador_id_filtro=cobrador_id_filtro
        )

    # --- Filtro de parcelas do dia ---
    query_parcelas = (
        db.session.query(Parcela, Cliente)
        .join(Emprestimo, Parcela.emprestimo_id == Emprestimo.id)
        .join(Cliente, Emprestimo.cliente_id == Cliente.id)
        .filter(Parcela.data_vencimento == hoje)
        .filter(Cliente.regiao_id.in_(regioes_ids))
    )

    if cobrador_id_filtro:
        query_parcelas = query_parcelas.filter(Cliente.cobrador_id == cobrador_id_filtro)

    parcelas_hoje = query_parcelas.all()

    total_pago_hoje = sum(parcela.valor_pago for parcela, _ in parcelas_hoje if parcela.status in ["pago", "parcialmente_paga"])
    total_a_receber = sum(parcela.valor for parcela, _ in parcelas_hoje)
    total_nao_recebido = total_a_receber - total_pago_hoje

    # --- Clientes filtrados ---
    query_clientes = Cliente.query.filter(Cliente.regiao_id.in_(regioes_ids))
    if cobrador_id_filtro:
        query_clientes = query_clientes.filter(Cliente.cobrador_id == cobrador_id_filtro)
    clientes = query_clientes.all()

    dashboard = []
    totais_pendentes = {}
    totais_atrasados = {}

    for cliente in clientes:
        cliente_total = 0.0
        cliente_recebido = 0.0
        cliente_nao_recebido = 0.0
        parcelas_info = []
        emprestimos = Emprestimo.query.filter_by(cliente_id=cliente.id).all()

        for emprestimo in emprestimos:
            for parcela in emprestimo.parcelas:
                valor = float(parcela.valor or 0)
                valor_pago = float(parcela.valor_pago or 0)
                cliente_total += valor

                if parcela.status == "pago":
                    cliente_recebido += valor
                else:
                    cliente_recebido += valor_pago
                    cliente_nao_recebido += (valor - valor_pago)

                parcelas_info.append({
                    "id": parcela.id,
                    "numero_parcela": parcela.numero_parcela,
                    "valor": valor,
                    "valor_pago": valor_pago,
                    "data_vencimento": parcela.data_vencimento,
                    "status": parcela.status
                })

        total_pendente = (
            db.session.query(func.sum(Parcela.valor - Parcela.valor_pago))
            .join(Emprestimo)
            .filter(Emprestimo.cliente_id == cliente.id, Parcela.status != "pago")
            .scalar() or 0.0
        )

        total_atrasado = (
            db.session.query(func.sum(Parcela.valor - Parcela.valor_pago))
            .join(Emprestimo)
            .filter(
                Emprestimo.cliente_id == cliente.id,
                Parcela.status != "pago",
                Parcela.data_vencimento < hoje
            )
            .scalar() or 0.0
        )

        totais_pendentes[cliente.id] = round(total_pendente, 2)
        totais_atrasados[cliente.id] = round(total_atrasado, 2)

        dashboard.append({
            "cliente": cliente,
            "emprestimos": emprestimos,
            "parcelas": parcelas_info,
            "total_cliente": cliente_total,
            "recebido_cliente": cliente_recebido,
            "nao_recebido_cliente": cliente_nao_recebido
        })

    return render_template(
        "dashboard_cobrador.html",
        dashboard=dashboard,
        parcelas_hoje=parcelas_hoje,
        total_a_receber=total_a_receber,
        total_pago_hoje=total_pago_hoje,
        total_nao_recebido=total_nao_recebido,
        now=now,
        totais_pendentes=totais_pendentes,
        totais_atrasados=totais_atrasados,
        hoje=hoje.strftime("%d/%m/%Y"),
        data_filtro_value=hoje.strftime("%Y-%m-%d"),
        regioes=Regiao.query.all(),
        cobradores=Usuario.query.filter_by(tipo="cobrador").all(),
        regiao_id_filtro=regiao_id_filtro,
        cobrador_id_filtro=cobrador_id_filtro
    )


@app.route("/receber_pagamento/<int:parcela_id>", methods=["POST"])
def receber_pagamento(parcela_id):
    if "usuario" not in session:
        flash("Faça login primeiro!", "danger")
        return redirect(url_for("login"))

    parcela = Parcela.query.get_or_404(parcela_id)
    valor_pago = float(request.form.get("valor_pago", 0))

    if valor_pago <= 0:
        flash("Valor inválido!", "danger")
        return redirect(url_for("dashboard_cobrador"))

    valor_restante = parcela.valor - parcela.valor_pago

    if valor_pago >= valor_restante:
        parcela.valor_pago = parcela.valor
        parcela.status = "pago"
        flash(f"Parcela {parcela.numero_parcela} paga completamente!", "success")
    else:
        parcela.valor_pago += valor_pago
        parcela.status = "parcialmente_paga"
        flash(f"Pagamento parcial de R$ {valor_pago:.2f} registrado para parcela {parcela.numero_parcela}!", "success")

    pagamento = Pagamento(
        emprestimo_id=parcela.emprestimo_id,
        parcela_id=parcela.id,
        valor=valor_pago,
        data_pagamento=datetime.now()
    )

    db.session.add(pagamento)

     #atualiza o total pago e status do empréstimo
    emprestimo = parcela.emprestimo
    emprestimo.total_pago = sum(p.valor_pago for p in emprestimo.parcelas)

    if emprestimo.total_pago >= emprestimo.valor_total:
        emprestimo.status = "quitado"
    else:
        emprestimo.status = "em aberto"

    db.session.commit()

    if session["tipo"] == "admin":
        return redirect(url_for("dashboard_admin"))
    else:
        return redirect(url_for("dashboard_cobrador"))


@app.route("/editar_pagamento/<int:pagamento_id>", methods=["POST"])
def editar_pagamento(pagamento_id):
    if "usuario" not in session:
        flash("Faça login primeiro!", "danger")
        return redirect(url_for("login"))

    pagamento = Pagamento.query.get_or_404(pagamento_id)
    parcela = Parcela.query.get(pagamento.parcela_id)

    if not parcela:
        flash("Parcela não encontrada!", "danger")
        return redirect(url_for("dashboard_cobrador"))

    novo_valor = float(request.form.get("novo_valor", 0))

    if novo_valor <= 0:
        flash("Valor inválido!", "danger")
        return redirect(url_for("dashboard_cobrador"))

    diferenca = novo_valor - pagamento.valor

    parcela.valor_pago += diferenca
    pagamento.valor = novo_valor

    if parcela.valor_pago >= parcela.valor:
        parcela.valor_pago = parcela.valor
        parcela.status = "pago"
    elif parcela.valor_pago > 0:
        parcela.status = "parcialmente_paga"
    else:
        parcela.valor_pago = 0
        parcela.status = "pendente"

    db.session.commit()
    flash("Pagamento editado com sucesso!", "success")

    if session["tipo"] == "admin":
        return redirect(url_for("dashboard_admin"))
    else:
        return redirect(url_for("dashboard_cobrador"))


@app.route("/cancelar_pagamento/<int:pagamento_id>", methods=["POST"])
def cancelar_pagamento(pagamento_id):
    if "usuario" not in session:
        flash("Faça login primeiro!", "danger")
        return redirect(url_for("login"))

    pagamento = Pagamento.query.get_or_404(pagamento_id)
    parcela = Parcela.query.get(pagamento.parcela_id)

    if parcela:
        parcela.valor_pago -= pagamento.valor

        if parcela.valor_pago <= 0:
            parcela.valor_pago = 0
            parcela.status = "pendente"
        elif parcela.valor_pago < parcela.valor:
            parcela.status = "parcialmente_paga"

    db.session.delete(pagamento)
    db.session.commit()

    flash(f"Pagamento cancelado! Valor de R$ {pagamento.valor:.2f} devolvido à parcela.", "warning")

    if session["tipo"] == "admin":
        return redirect(url_for("dashboard_admin"))
    else:
        return redirect(url_for("dashboard_cobrador"))


@app.route("/cadastro_cliente", methods=["GET", "POST"])
def cadastro_cliente():
    cobradores = Usuario.query.filter_by(tipo="cobrador").all()

    if request.method == "POST":
        nome = request.form["nome"]
        telefone = request.form["telefone"]
        endereco = request.form["endereco"]
        regiao_id = request.form["regiao_id"]
        cobrador_id = request.form["cobrador_id"]

        novo_cliente = Cliente(
            nome=nome,
            telefone=telefone,
            endereco=endereco,
            regiao_id=regiao_id,
            cobrador_id=cobrador_id
        )
        db.session.add(novo_cliente)
        db.session.commit()

        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for("dashboard_admin"))
    #aqui busca todas as regiões
    regioes_objs = Regiao.query.all()

    #aqui faz a conversão antes de renderizar para o template
    regioes = []
    for r in regioes_objs:
        regioes.append({
            "id": r.id,
            "nome": r.nome,
            "cobradores": [{"id": c.id, "usuario": c.usuario} for c in r.cobradores]
        })

    return render_template("cadastro_cliente.html", regioes=regioes, cobradores=cobradores)


@app.route("/cadastrar_cobrador", methods=["GET", "POST"])
def cadastrar_cobrador():
    if "usuario" not in session or session["tipo"] != "admin":
        flash("Acesso negado.", "danger")
        return redirect(url_for("login"))

    regioes = Regiao.query.all()

    if request.method == "POST":
        usuario_nome = request.form.get("usuario")
        senha = request.form.get("senha")
        tipo = request.form.get("tipo") #admin ou cobrador
        regiao_id = request.form.get("regiao_id", type=int)

        novo_cobrador = Usuario(usuario=usuario_nome, senha=senha, tipo=tipo)

        if tipo == "cobrador" and regiao_id:
            regiao = Regiao.query.get(int(regiao_id))
            if regiao:
                novo_cobrador.regioes.append(regiao)

        db.session.add(novo_cobrador)
        db.session.commit()

        flash(f"{tipo.capitalize()} cadastrado com sucesso!", "success")
        return redirect(url_for("dashboard_admin"))

    return render_template("cadastrar_cobrador.html", regioes=regioes)


@app.route("/trocar_usuario")
def trocar_usuario():
    session.clear()
    flash("Você saiu do sistema. Faça login novamente", "success")
    return redirect(url_for("login"))


@app.route("/listar_clientes")
def listar_clientes():
    if session.get("tipo") != "admin":
        flash("Acesso negado!", "danger")
        return redirect(url_for("login"))

    page = request.args.get("page", 1, type=int)
    per_page = 10 #mostra 10 clientes a cada pagina 

    clientes = Cliente.query.paginate(page=page, per_page=per_page)
    qtd_clientes = Cliente.query.count()
    return render_template("listar_clientes.html", clientes=clientes, qtd_clientes=qtd_clientes, pagination=clientes)

@app.route("/resumo_clientes")
def resumo_clientes():
    if "usuario" not in session:
        flash("Faça login primeiro!", "danger")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session.get("usuario_id"))

    if not usuario or usuario.tipo not in ["admin", "cobrador"]:
        flash("Acesso negado", "danger")
        return redirect(url_for("login"))

    hoje = datetime.now().date()
    regioes_ids = [r.id for r in usuario.regioes]

    #carregar clientes das regioes
    clientes = Cliente.query.filter(Cliente.regiao_id.in_(regioes_ids)).order_by(Cliente.nome.asc()).all()
    dashboard = []
    totais_pendentes = {}
    totais_atrasados = {}

    for cliente in clientes:
        emprestimos = Emprestimo.query.filter_by(cliente_id=cliente.id).all()

        total_pendente = (
            db.session.query(func.sum(Parcela.valor - Parcela.valor_pago))
            .join(Emprestimo)
            .filter(Emprestimo.cliente_id == cliente.id, Parcela.status != "pago")
            .scalar() or 0.0
            )

        total_atrasado = (
            db.session.query(func.sum(Parcela.valor - Parcela.valor_pago))
            .join(Emprestimo)
            .filter(
                Emprestimo.cliente_id == cliente.id,
                Parcela.status != "pago",
                Parcela.data_vencimento < hoje
                )
            .scalar() or 0.0
            )

        totais_pendentes[cliente.id] = round(total_pendente, 2)
        totais_atrasados[cliente.id] = round(total_atrasado, 2)

        dashboard.append({
            "cliente": cliente,
            "emprestimos": emprestimos
            })

    return render_template(
        "resumo_clientes.html",
        dashboard=dashboard,
        hoje=hoje,
        totais_pendentes=totais_pendentes,
        totais_atrasados=totais_atrasados
        )


@app.route("/excluir_clientes/<int:id>", methods=["POST"])
def excluir_clientes(id):
    cliente = Cliente.query.get_or_404(id)

    db.session.delete(cliente)
    db.session.commit()
    flash(f"Cliente {cliente.nome} excluído com sucesso!", "success")
    return redirect(url_for("listar_clientes"))

@app.route("/listar_cobradores")
def listar_cobradores():
    if session.get("tipo") != "admin":
        flash("Acesso negado!", "danger")
        return redirect(url_for("login"))

    usuario = Usuario.query.all()
    return render_template("listar_cobradores.html", usuario=usuario)


@app.route("/excluir_cobrador/<int:id>", methods=["POST"])
def excluir_cobrador(id):
    cobrador = Usuario.query.get_or_404(id)

    if cobrador.tipo != "cobrador":
        flash("Não é possível excluir este usuário", "danger")
        return redirect(url_for("listar_cobradores"))

    db.session.delete(cobrador)
    db.session.commit()
    flash(f"Cobrador {cobrador.usuario} excluído com sucesso!", "success")
    return redirect(url_for("listar_cobradores"))


@app.route("/editar_cliente/<int:id>", methods=["POST", "GET"])
def editar_cliente(id):
    if "usuario" not in session:
        flash("Faça login primeiro!", "danger")
        return redirect(url_for("login"))

    cliente = Cliente.query.get_or_404(id)

    nome = request.form.get("nome")
    telefone = request.form.get("telefone")
    endereco = request.form.get("endereco")

    cliente.nome = nome
    cliente.telefone = telefone
    cliente.endereco = endereco

    db.session.commit()

    flash(f"Cliente {cliente.nome} atualizado com sucesso!", "success")
    return redirect(url_for("listar_clientes"))


@app.route("/excluir_cliente/<int:id>", methods=["POST", "GET"])
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    for emprestimo in cliente.emprestimos:
        for parcela in emprestimo.parcelas:
            db.session.delete(parcela)
        db.session.delete(emprestimo)
    db.session.delete(cliente)
    db.session.commit()

    flash("Cliente e todos os empréstimos excluídos com sucesso!", "danger")
    return redirect(url_for("listar_clientes"))


@app.route("/editar_emprestimo/<int:id>", methods=["POST", "GET"])
def editar_emprestimo(id):
    emprestimo = Emprestimo.query.get_or_404(id)

    # Atualiza os campos do empréstimo
    emprestimo.valor = float(request.form.get("valor", emprestimo.valor))
    emprestimo.porcentagem = float(request.form.get("porcentagem", emprestimo.porcentagem))
    emprestimo.frequencia = request.form.get("frequencia", emprestimo.frequencia)

    # Tratar qtd_parcelas para não dar erro se estiver vazio
    qtd_parcelas_str = request.form.get("qtd_parcelas")
    if qtd_parcelas_str and qtd_parcelas_str.isdigit():
        emprestimo.qtd_parcelas = int(qtd_parcelas_str)
    else:
        emprestimo.qtd_parcelas = len(emprestimo.parcelas)

    # Data do empréstimo
    data_str = request.form.get("data_emprestimo")
    if data_str:
        emprestimo.data_emprestimo = datetime.strptime(data_str, "%Y-%m-%d").date()

    # Calcula valor total atualizado
    emprestimo.valor_total = emprestimo.valor + (emprestimo.valor * (emprestimo.porcentagem / 100))

    # Remove parcelas antigas
    for p in list(emprestimo.parcelas):
        db.session.delete(p)
    db.session.flush()

    # Gera novas parcelas
    parcelas = emprestimo.gerar_parcelas()
    for parcela in parcelas:
        parcela.emprestimo_id = emprestimo.id
        db.session.add(parcela)

    # Atualiza total_pago e status do empréstimo
    emprestimo.total_pago = sum(p.valor_pago or 0 for p in parcelas)
    emprestimo.status = "quitado" if emprestimo.total_pago >= emprestimo.valor_total else "em aberto"

    db.session.commit()
    flash("Empréstimo e parcelas atualizadas com sucesso!", "success")
    return redirect(url_for("dashboard_admin"))




@app.route("/excluir_emprestimo/<int:id>")
def excluir_emprestimo(id):
    emprestimo = Emprestimo.query.get_or_404(id)

    nome_cliente = emprestimo.cliente.nome
    frequencia = emprestimo.frequencia

    for parcela in emprestimo.parcelas:
        db.session.delete(parcela)
    db.session.delete(emprestimo)
    db.session.commit()
    flash(f"Empréstimo ({frequencia.capitalize()}) de {nome_cliente} excluído!", "danger")
    return redirect(url_for("dashboard_admin"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu com sucesso!", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
