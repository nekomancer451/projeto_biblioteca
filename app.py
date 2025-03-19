from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mail import Mail, Message
import requests
import logging
import re
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
import random
import string 

app = Flask(__name__)
app.secret_key = "sua_chave_secreta"

# Configurações do Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///biblioteca.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    autor = db.Column(db.String(), nullable=False)
    isbn = db.Column(db.String(13), unique=True, nullable=False)
    editora = db.Column(db.String(120))
    ano = db.Column(db.Integer())
    categoria = db.Column(db.String(50))
    sinopse = db.Column(db.Text())
    capa_url = db.Column(db.String(200))
    status = db.Column(db.String(20), default='disponivel')
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

# Inicialização do LoginManager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

# Configuração do Flask-Mail
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "seuemail@gmail.com"
app.config["MAIL_PASSWORD"] = "suasenha"
app.config["MAIL_DEFAULT_SENDER"] = "seuemail@gmail.com"

mail = Mail(app)

# Função para gerar token aleatório
def gerar_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

# Tempo de expiração do token (30 minutos)
TOKEN_EXPIRATION_TIME = timedelta(minutes=30)

# Dicionário para armazenar tokens e horários de geração
tokens_verificacao = {}

# Rota principal (dashboard)
@app.route("/")
@login_required
def dashboard():
    return render_template("index.html")

# Rota de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()        
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for("dashboard"))
        flash("Login inválido. Verifique o nome de usuário e a senha.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")

# Rota de registro
# Rota de registro
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form.get("confirm_password")
        
        if password != confirm_password:
            flash("As senhas não coincidem!", "danger")
            return redirect(url_for("registro"))
        
        # Gere um token único e armazene com o horário atual
        token = gerar_token()
        tokens_verificacao[email] = {
            "token": token,
            "criado_em": datetime.utcnow()  # Horário UTC
        }

        # Enviar e-mail de verificação
        link_verificacao = url_for("verificar_email", token=token, _external=True)
        mensagem = Message("Confirme seu e-mail", recipients=[email])
        mensagem.body = f"Olá, {username}!\n\nClique no link para verificar seu e-mail: {link_verificacao}\n\nO link expira em 30 minutos."
        mail.send(mensagem)

        flash("Um e-mail de verificação foi enviado para você. Confirme seu cadastro!", "info")
        return redirect(url_for("registro"))

    return render_template("registro.html")

# Rota de verificação de e-mail
@app.route("/verificar/<token>")
def verificar_email(token):
    for email, data in tokens_verificacao.items():
        token_armazenado = data["token"]
        criado_em = data["criado_em"]

        # Verifica se o token é válido e se ainda está dentro do tempo de expiração
        if token_armazenado == token:
            if datetime.utcnow() - criado_em < TOKEN_EXPIRATION_TIME:
                flash(f"E-mail {email} verificado com sucesso!", "success")
                tokens_verificacao.pop(email, None)  # Remove o token após o uso
                return redirect(url_for("login"))
            else:
                flash("Token expirado! Solicite um novo e-mail de verificação.", "danger")
                tokens_verificacao.pop(email, None)  # Remove token expirado
                return redirect(url_for("registro"))

    flash("Token inválido ou expirado!", "danger")
    return redirect(url_for("registro"))

# Rota de logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Você saiu da sessão.", "info")
    return redirect(url_for('login'))

# Rota para listar livros
@app.route("/livros")
@login_required
def listar_livros():
    search = request.args.get('search', '')
    ordenar_por = request.args.get('ordenar_por', 'titulo_asc')
    query = Book.query
    if search:
        query = query.filter(Book.titulo.ilike(f'%{search}%'))
    if ordenar_por == 'titulo_asc':
        query = query.order_by(Book.titulo.asc())
    elif ordenar_por == 'titulo_desc':
        query = query.order_by(Book.titulo.desc())
    elif ordenar_por == 'ano_asc':
        query = query.order_by(Book.ano.asc())
    elif ordenar_por == 'ano_desc':
        query = query.order_by(Book.ano.desc())
    livros = query.all()
    return render_template("listar_livros.html", livros=livros, search=search)

# Rota para adicionar livro manualmente
@app.route("/adicionar_livro", methods=["GET", "POST"])
@login_required
def adicionar_livro():
    if request.method == "POST":
        try:
            novo_livro = Book(
                titulo=request.form["titulo"],
                autor=request.form["autor"],
                isbn=request.form["isbn"],
                editora=request.form["editora"],
                ano=int(request.form["ano"]) if request.form["ano"].isdigit() else None,
                categoria=request.form["categoria"],
                sinopse=request.form.get("sinopse", "")
            )
            db.session.add(novo_livro)
            db.session.commit()
            flash('Livro adicionado com sucesso!', 'success')
            return redirect(url_for("listar_livros"))
        except IntegrityError:
            db.session.rollback()
            flash('Erro: ISBN já cadastrado ou autor inválido!', 'danger')
        except ValueError as e:
            flash(f"Erro: {str(e)}", 'danger')
    return render_template("adicionar_livro.html")

# Rota para buscar ISBN em múltiplas fontes (Google Books e Open Library)
@app.route("/buscar_isbn", methods=["GET", "POST"])
@login_required
def buscar_isbn():
    book_info = None
    if request.method == "POST":
        isbn = request.form.get("isbn")
        google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&langRestrict=pt-BR"
        try:
            google_response = requests.get(google_url, timeout=5)
            if google_response.status_code == 200:
                google_data = google_response.json()
                if google_data.get("totalItems", 0) > 0:
                    volume_info = google_data["items"][0]["volumeInfo"]
                    publisher = volume_info.get("publisher", "Sem informação")
                    published_date = volume_info.get("publishedDate", "Sem informação")
                    book_info = {
                        "title": volume_info.get("title"),
                        "authors": volume_info.get("authors"),
                        "publisher": publisher,
                        "publishedDate": published_date,
                        "description": volume_info.get("description"),
                        "isbn": isbn
                    }
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição para o Google Books: {e}")

        if not book_info:
            openlibrary_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
            try:
                openlibrary_response = requests.get(openlibrary_url, timeout=5)
                if openlibrary_response.status_code == 200:
                    openlibrary_data = openlibrary_response.json()
                    key = f"ISBN:{isbn}"
                    if key in openlibrary_data:
                        data = openlibrary_data[key]
                        book_info = {
                            "title": data.get("title"),
                            "authors": [author["name"] for author in data.get("authors", [])] if data.get("authors") else [],
                            "publisher": data.get("publishers", [{}])[0].get("name") if data.get("publishers") else "",
                            "publishedDate": data.get("publish_date"),
                            "isbn": isbn,
                            "description": data.get("notes") if isinstance(data.get("notes"), str) else ""
                        }
            except requests.exceptions.RequestException as e:
                logging.error(f"Erro na requisição para a Open Library: {e}")
    return render_template("buscar_isbn.html", book_info=book_info)

# Rota para salvar livro obtido via busca por ISBN ou título
@app.route("/save", methods=["POST"])
@login_required
def save_book():
    try:
        published_date = request.form.get("publishedDate", "")
        ano = None
        if published_date:
            match = re.search(r'\d{4}', published_date)
            if match:
                ano = int(match.group())
    
        novo_livro = Book(
            titulo=request.form.get("title"),
            autor=request.form.get("author") or "Desconhecido",
            isbn=request.form.get("isbn"),
            editora=request.form.get("publisher"),
            ano=ano,
            categoria=request.form.get("categoria", ""),
            sinopse=request.form.get("description", "")
        )
    
        db.session.add(novo_livro)
        db.session.commit()
        flash("Livro adicionado com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro: ISBN já cadastrado!", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar livro: {str(e)}", "danger")
    return redirect(url_for("listar_livros"))

# Rota para buscar livro por título nas fontes Google Books e Open Library
@app.route("/buscar_titulo", methods=["GET", "POST"])
@login_required
def buscar_titulo():
    resultados = []
    if request.method == "GET" and "titulo" in request.args:
        titulo = request.args.get("titulo")
        google_url = f"https://www.googleapis.com/books/v1/volumes?q={titulo}&langRestrict=pt-BR"
        try:
            google_response = requests.get(google_url, timeout=5)
            if google_response.status_code == 200:
                google_data = google_response.json()
                for item in google_data.get("items", []):
                    volume_info = item["volumeInfo"]
                    published_date = volume_info.get("publishedDate", "Sem data")
                    ano = published_date[:4] if published_date != "Sem data" else "Sem data"
                    resultados.append({
                        "titulo": volume_info.get("title", "Sem título"),
                        "autor": ", ".join(volume_info.get("authors", ["Desconhecido"])),
                        "isbn": volume_info.get("industryIdentifiers", [{}])[0].get("identifier", "Sem ISBN"),
                        "editora": volume_info.get("publisher", "Sem editora"),
                        "ano": ano,
                        "descricao": volume_info.get("description", ""),
                        "fonte": "Google Books"
                    })
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição para o Google Books: {e}")

        openlibrary_url = f"https://openlibrary.org/search.json?title={titulo}"
        try:
            openlibrary_response = requests.get(openlibrary_url, timeout=5)
            if openlibrary_response.status_code == 200:
                openlibrary_data = openlibrary_response.json()
                for doc in openlibrary_data.get("docs", []):
                    resultados.append({
                        "titulo": doc.get("title", "Sem título"),
                        "autor": ", ".join(doc.get("author_name", ["Desconhecido"])),
                        "isbn": doc.get("isbn", ["Sem ISBN"])[0] if "isbn" in doc else "Sem ISBN",
                        "editora": ", ".join(doc.get("publisher", ["Sem editora"])),
                        "ano": doc.get("first_publish_year", "Sem data"),
                        "descricao": doc.get("subject", "Sem descrição"),
                        "fonte": "Open Library"
                    })
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição para a Open Library: {e}")
    return render_template("buscar_titulo.html", resultados=resultados)

# Rota para editar livro
@app.route("/editar/<isbn>", methods=["GET", "POST"])
@login_required
def editar_livro(isbn):
    livro = Book.query.filter_by(isbn=isbn).first_or_404()
    
    if request.method == "POST":
        try:
            livro.titulo = request.form["titulo"]
            livro.autor = request.form["autor"]
            livro.editora = request.form["editora"]
            livro.ano = int(request.form["ano"]) if request.form["ano"].isdigit() else None
            livro.categoria = request.form["categoria"]
            livro.sinopse = request.form.get("sinopse", "")
            livro.isbn = request.form["isbn"]

            db.session.commit()
            flash('Livro atualizado com sucesso!', 'success')
            return redirect(url_for("listar_livros"))
        except IntegrityError:
            db.session.rollback()
            flash('Erro ao atualizar o livro!', 'danger')

    return render_template("editar_livro.html", livro=livro)

# Rota para excluir livro
@app.route("/excluir/<isbn>", methods=["POST"])
@login_required
def excluir_livro(isbn):
    livro = Book.query.filter_by(isbn=isbn).first_or_404()
    try:
        db.session.delete(livro)
        db.session.commit()
        flash('Livro excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir livro!', 'danger')
    return redirect(url_for("listar_livros"))

if __name__ == "__main__":
    app.run(debug=True)
