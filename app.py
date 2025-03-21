from flask import Flask, render_template, request, redirect, url_for, flash
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import requests  # para requisições externas
import sqlite3

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = "sua_chave_secreta"

# Configurações do Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///biblioteca.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de Usuário com flag de senha temporária
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    # Campo para identificar se o usuário ainda está usando a senha temporária
    senha_temporaria = db.Column(db.Boolean, default=True)

# Modelo para Livro
class Book(db.Model):
    __tablename__ = 'book'  # Nome explícito da tabela
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column("title", db.String(200), nullable=False)
    autor = db.Column("authors", db.String(), nullable=False)
    isbn = db.Column("isbn", db.String(13), unique=True, nullable=False)
    editora = db.Column("publisher", db.String(120))
    ano = db.Column("ano", db.Integer())
    categoria = db.Column("category", db.String(50))
    sinopse = db.Column("sinopsis", db.Text())
    capa_url = db.Column("cover_url", db.String(200))
    status = db.Column("status", db.String(20), default='disponivel')
    data_criacao = db.Column("created_at", db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Book {self.titulo}>'
    def as_dict(self):
        return {
            "title": self.titulo,
            "authors": self.autor,
            "isbn": self.isbn,
            "publisher": self.editora,
            "published_date": self.ano,
            "category": self.categoria,
            "sinopsis": self.sinopse,
            "cover_url": self.capa_url,
            "status": self.status,
            "created_at": self.data_criacao
        }

# Função para criar todas as tabelas no banco de dados
def criar_tabelas():
    with app.app_context():  # Necessário para usar o contexto do Flask
        db.create_all()  # Cria as tabelas baseadas nos modelos

# Inicialização do LoginManager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Função de controle de acesso
def usuario_eh_admin():
    usuario = current_user
    return usuario.is_admin if usuario else False

# Função para adicionar um usuário no banco com senha temporária
def adicionar_usuario_no_banco(username, senha_temporaria):
    hashed_password = generate_password_hash(senha_temporaria, method='pbkdf2:sha256')
    novo_usuario = User(username=username, password=hashed_password, senha_temporaria=True)
    db.session.add(novo_usuario)
    db.session.commit()

# Função para criar um usuário (permitido apenas para admin)
def criar_usuario(username):
    logging.debug(f"Tentando criar usuário: {username}")
    if not usuario_eh_admin():
        logging.debug("Usuário atual não é administrador.")
        raise Exception("Somente administradores podem criar contas.")
    
    senha_temporaria = "senha_temporal_123"  # Senha temporária
    try:
        adicionar_usuario_no_banco(username, senha_temporaria)
        logging.debug(f"Usuário {username} criado com sucesso.")
    except IntegrityError:
        db.session.rollback()
        logging.debug(f"Erro ao criar usuário {username}: Nome de usuário já existe.")
        raise Exception("Erro: Nome de usuário já existe.")

# Função para verificar se o usuário já alterou a senha temporária
def senha_foi_alterada(username):
    usuario = User.query.filter_by(username=username).first()
    # Aqui, usamos o campo senha_temporaria para controlar
    return usuario and not usuario.senha_temporaria

# Função para atualizar a senha no banco e marcar que a senha foi alterada
def atualizar_senha_no_banco(username, nova_senha):
    usuario = User.query.filter_by(username=username).first()
    if usuario:
        usuario.password = generate_password_hash(nova_senha, method='pbkdf2:sha256')
        usuario.senha_temporaria = False
        db.session.commit()

# Função para mudança de senha após o primeiro login
def mudar_senha(username, nova_senha):
    if senha_foi_alterada(username):
        raise Exception("A senha já foi alterada.")
    atualizar_senha_no_banco(username, nova_senha)

# Criação do banco e do usuário administrador inicial (Nana)
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="Nana").first():
        admin = User(
            username="Nana",
            password=generate_password_hash("admin123", method="pbkdf2:sha256"),
            is_admin=True,
            senha_temporaria=False  # senha definida definitivamente
        )
        db.session.add(admin)
        db.session.commit()

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

@app.route('/admin/criar_usuario', methods=['GET', 'POST'])
@login_required
def criar_usuario_admin():
    # Verifica se o usuário logado é administrador
    if not current_user.is_admin:
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        if password != confirm_password:
            flash("As senhas não coincidem!", "danger")
            return redirect(url_for("criar_usuario_admin"))
        
        # Cria o usuário com a senha definida (não como temporária)
        try:
            hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
            novo_usuario = User(
                username=username,
                password=hashed_password,
                is_admin=False,        # ou True, se desejar criar outro admin
                senha_temporaria=False # senha já definida
            )
            db.session.add(novo_usuario)
            db.session.commit()
            flash("Usuário criado com sucesso!", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Erro: Nome de usuário já existe.", "danger")
        
        return redirect(url_for("dashboard"))
    
    return render_template("criar_usuario_admin.html")

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
@app.route("/adicionar", methods=["GET", "POST"])
@login_required
def adicionar_livro():
    if request.method == "POST":
        titulo = request.form.get("titulo")
        autor = request.form.get("autor")
        isbn = request.form.get("isbn")
        editora = request.form.get("editora")
        ano = request.form.get("ano")
        categoria = request.form.get("categoria")

        if not titulo or not autor or not isbn:
            flash("Título, Autor e ISBN são obrigatórios!", "danger")
            return redirect(url_for("adicionar_livro"))

        # Verifica se já existe um livro com o mesmo ISBN
        livro_existente = Book.query.filter_by(isbn=isbn).first()
        if livro_existente:
            flash("Este livro já existe no sistema!", "warning")
            return redirect(url_for("listar_livros"))

        novo_livro = Book(
            titulo=titulo,
            autor=autor,
            isbn=isbn,
            editora=editora,
            ano=int(ano) if ano and ano.isdigit() else None,
            categoria=categoria,
            status="disponivel"
        )

        try:
            db.session.add(novo_livro)
            db.session.commit()
            flash("Livro adicionado com sucesso!", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao adicionar livro. Verifique os dados inseridos.", "danger")

        return redirect(url_for("listar_livros"))

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
from flask import request, redirect, url_for
from datetime import datetime

# Rota para salvar livro obtido via busca por ISBN ou título
@app.route("/save", methods=["POST"])
def save_book():
    title = request.form.get("title")
    authors = request.form.get("authors")
    publisher = request.form.get("publisher")
    published_date = request.form.get("published_date")
    isbn = request.form.get("isbn")

    # Verifica se o ISBN já existe no banco de dados
    existing_book = Book.query.filter_by(isbn=isbn).first()
    if existing_book:
        return "Este livro já está na base de dados.", 400

    # Extrai o ano da data de publicação (caso esteja no formato "YYYY" ou "YYYY-MM-DD")
    year = published_date[:4] if published_date else "0"
    try:
        ano = int(year)
    except ValueError:
        ano = 0

    # Criação do objeto Book (mapeando os campos para os nomes no banco)
    book = Book(
        titulo=title,  # 'title' da interface vai para 'titulo' no modelo
        autor=authors,  # 'authors' da interface vai para 'autor' no modelo
        isbn=isbn,
        editora=publisher,  # 'publisher' da interface vai para 'editora' no modelo
        ano=ano
    )

    # Adiciona o livro ao banco de dados
    db.session.add(book)
    db.session.commit()

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
        livro.titulo = request.form["titulo"]
        livro.autor = request.form["autor"]
        livro.isbn = request.form["isbn"]
        livro.editora = request.form["editora"]
        livro.ano = int(request.form["ano"]) if request.form["ano"].isdigit() else None
        livro.categoria = request.form["categoria"]
        livro.sinopse = request.form.get("sinopse", "")
        db.session.commit()
        flash("Livro atualizado com sucesso!", "success")
        return redirect(url_for("listar_livros"))
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

from app import db
db.create_all()
