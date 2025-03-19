from flask import Flask, render_template, request, redirect, url_for, flash
import requests
import logging
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.secret_key = "sua_chave_secreta"  # Substitua por uma chave secreta real

# Configurações do Flask-SQLAlchemy
app.config['SECRET_KEY'] = 'sua_chave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
db = SQLAlchemy(app)  # Inicializa SQLAlchemy após as configurações

# Modelo de Usuário
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

# Modelos
class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('author.id'), nullable=False)
    autor = db.relationship('Author', backref=db.backref('books', lazy=True))
    isbn = db.Column(db.String(13), unique=True, nullable=False)
    editora = db.Column(db.String(120))
    ano = db.Column(db.Integer)
    categoria = db.Column(db.String(50))
    sinopse = db.Column(db.Text)
    capa_url = db.Column(db.String(200))
    status = db.Column(db.String(20), default='disponivel')
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

# Inicializa o LoginManager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Cria o banco de dados (caso ainda não exista)
with app.app_context():
    db.create_all()

# Configuração do logging
logging.basicConfig(level=logging.DEBUG)

# Rota principal
@app.route("/")
@login_required
def dashboard():
    return render_template("index.html")

# Rotas de autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()        
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(url_for("dashboard"))
        return "Login inválido. Verifique o nome de usuário e a senha.", 401
    return render_template("login.html")

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = generate_password_hash(request.form.get('password'))
        novo_usuario = User(username=username, email=email, password=password)
        db.session.add(novo_usuario)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/logout')
def logout():
    logout_user()
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
    autores = Author.query.order_by(Author.nome).all()
    if request.method == "POST":
        try:
            autor_id = int(request.form["autor"])
            novo_livro = Book(
                titulo=request.form["titulo"],
                autor_id=autor_id,
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
            flash('ISBN já cadastrado!', 'danger')
    return render_template("adicionar_livro.html", autores=autores)

# Rotas de autores
@app.route("/autores", methods=["GET", "POST"])
@login_required
def adicionar_autor():
    if request.method == "POST":
        nome_autor = request.form["nome_autor"].strip()
        if nome_autor:
            try:
                novo_autor = Author(nome=nome_autor)
                db.session.add(novo_autor)
                db.session.commit()
                flash('Autor adicionado com sucesso!', 'success')
            except IntegrityError:
                db.session.rollback()
                flash('Este autor já existe!', 'danger')
        return redirect(url_for('adicionar_autor'))
    
    autores = Author.query.order_by(Author.nome).all()
    return render_template("adicionar_autor.html", autores=autores)

# Rota para buscar ISBN em múltiplas fontes
@app.route("/buscar_isbn", methods=["GET", "POST"])
@login_required
def buscar_isbn():
    book_info = None
    if request.method == "POST":
        isbn = request.form.get("isbn")
        # Tenta buscar via Google Books
        google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&langRestrict=pt-BR"
        google_response = requests.get(google_url)
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
        # Se não encontrar no Google, tenta buscar via Open Library
        if not book_info:
            openlibrary_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
            openlibrary_response = requests.get(openlibrary_url)
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
    return render_template("buscar_isbn.html", book_info=book_info)

# Rota para salvar livro vindo da busca por ISBN
@app.route("/save", methods=["POST"])
@login_required
def save_book():
    try:
        # Seleciona o primeiro autor, se houver
        authors_str = request.form.get("authors")
        if authors_str:
            first_author = authors_str.split(",")[0].strip()
            autor_obj = Author.query.filter_by(nome=first_author).first()
            if not autor_obj:
                autor_obj = Author(nome=first_author)
                db.session.add(autor_obj)
                db.session.commit()
            autor_id = autor_obj.id
        else:
            autor_id = None

        novo_livro = Book(
            titulo=request.form.get("title"),
            autor_id=autor_id,
            isbn=request.form.get("isbn"),
            editora=request.form.get("publisher"),
            ano=int(request.form.get("publishedDate")[:4]) if request.form.get("publishedDate") else None,
            categoria="",
            sinopse=request.form.get("description", "")
        )
        db.session.add(novo_livro)
        db.session.commit()
        flash("Livro adicionado com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("ISBN já cadastrado!", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar livro: {str(e)}", "danger")
    
    return redirect(url_for("listar_livros"))

# Rota para buscar livro por título
@app.route("/buscar_titulo", methods=["GET", "POST"])
@login_required
def buscar_titulo():
    resultados = []
    if request.method == "GET" and "titulo" in request.args:
        titulo = request.args.get("titulo")
        # Busca no Google Books
        google_url = f"https://www.googleapis.com/books/v1/volumes?q={titulo}&langRestrict=pt-BR"
        try:
            google_response = requests.get(google_url)
            if google_response.status_code == 200:
                google_data = google_response.json()
                for item in google_data.get("items", []):
                    volume_info = item["volumeInfo"]
                    resultados.append({
                        "titulo": volume_info.get("title", "Sem título"),
                        "autor": ", ".join(volume_info.get("authors", ["Desconhecido"])),
                        "isbn": volume_info.get("industryIdentifiers", [{}])[0].get("identifier", "Sem ISBN"),
                        "editora": volume_info.get("publisher", "Sem editora"),
                        "ano": volume_info.get("publishedDate", "Sem data")[:4],
                        "descricao": volume_info.get("description", ""),
                        "fonte": "Google Books"
                    })
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição para o Google Books: {e}")

        # Busca na Open Library
        openlibrary_url = f"https://openlibrary.org/search.json?title={titulo}"
        try:
            openlibrary_response = requests.get(openlibrary_url)
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
            livro.autor_id = int(request.form["autor"])  # Atualiza o autor via ID
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
