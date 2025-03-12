from flask import Flask, render_template, request, redirect, url_for
import requests
import logging
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "sua_chave_secreta"  # Substitua por uma chave secreta real

# Configurações do Flask-SQLAlchemy
app.config['SECRET_KEY'] = 'sua_chave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
db = SQLAlchemy(app)  # Inicializa SQLAlchemy após as configurações

# Modelo de Usuário (definido uma única vez após a inicialização do db)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

# Inicializa o LoginManager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Cria o banco de dados de usuários
with app.app_context():
    db.create_all()

# Configuração do logging
logging.basicConfig(level=logging.DEBUG)

# Função para obter conexão com o banco SQLite
def get_db_connection():
    conn = sqlite3.connect("biblioteca.db")
    cursor = conn.cursor()
    conn.row_factory = sqlite3.Row  # Permite acessar os dados por nome da coluna
    return conn

# Função para inicializar o banco de dados e criar a tabela, se necessário
def init_db():
    conn = sqlite3.connect('biblioteca.db')  # Conecta ao banco de dados (se não existir, será criado)
    cursor = conn.cursor()  # Cria o cursor para executar comandos SQL

    # Abre o arquivo SQL e executa as instruções contidas nele
    with open('criar_tabelas.sql', 'r') as file:
        cursor.executescript(file.read())  # Executa o script SQL que está no arquivo

    conn.commit()  # Confirma as mudanças no banco de dados
    conn.close()  # Fecha a conexão

# Função para carregar todos os livros (substituindo o carregar_livros do JSON)
def carregar_livros():
    conn = get_db_connection()
    livros = conn.execute("SELECT * FROM livros").fetchall()
    conn.close()
    return livros

# Função para salvar um livro (substituindo a função salvar_livros do JSON)
def salvar_livro(livro):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO livros (titulo, autor, isbn, editora, ano, categoria) VALUES (?, ?, ?, ?, ?, ?)",
            (livro["titulo"], livro["autor"], livro["isbn"], livro["editora"], livro["ano"], livro["categoria"])
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        logging.error("Erro ao inserir livro: " + str(e))
        conn.close()
        raise
    conn.close()

# Função para buscar livros por título utilizando uma query SQL
def buscar_livro_por_titulo(titulo):
    conn = get_db_connection()
    query = "SELECT * FROM livros WHERE lower(titulo) LIKE ?"
    livros = conn.execute(query, ('%' + titulo.lower() + '%',)).fetchall()
    conn.close()
    return livros

# Rota principal com busca por ISBN em múltiplas fontes
@app.route("/", methods=["GET", "POST"])
def index():
    book_info = None
    if request.method == "POST":
        isbn = request.form.get("isbn")
        
        # 1. Tenta buscar via Google Books
        google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&langRestrict=pt-BR"
        google_response = requests.get(google_url)
        if google_response.status_code == 200:
            google_data = google_response.json()
            if google_data.get("totalItems", 0) > 0:
             volume_info = google_data["items"][0]["volumeInfo"]
            # Acessa as informações de publisher e publishedDate
            publisher = volume_info.get("publisher", "Sem informação")
            published_date = volume_info.get("publishedDate", "Sem informação")
            # Adiciona essas informações ao dicionário que será enviado para o template
            book_info = {
                "title": volume_info.get("title"),
               "authors": volume_info.get("authors"),
                "publisher": publisher,
                "publishedDate": published_date,
                "description": volume_info.get("description"),
                "isbn": isbn
            }
        
        # 2. Se não encontrar no Google, tenta buscar via Open Library
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
        
        # Se desejar adicionar outras fontes gratuitas, você pode inserir novas chamadas aqui,
        # seguindo o mesmo padrão de verificação da resposta e extração dos dados.
        
    return render_template("index.html", book_info=book_info)

# Rota para salvar livro obtido via ISBN
@app.route("/save", methods=["POST"])
@login_required
def save_book():
    title = request.form.get("title")
    authors = request.form.get("authors")
    publisher = request.form.get("publisher")
    published_date = request.form.get("published_date")
    isbn = request.form.get("isbn")

    # Verifica se o ISBN já existe no banco de dados
    conn = get_db_connection()
    livro_existente = conn.execute("SELECT * FROM livros WHERE isbn = ?", (isbn,)).fetchone()
    conn.close()
    if livro_existente:
        return "Este livro já está na base de dados.", 400

    # Extrai o ano da data de publicação
    year = published_date[:4] if published_date else "0"
    try:
        ano = int(year)
    except ValueError:
        ano = 0

    book = {
        "titulo": title,
        "autor": authors,
        "isbn": isbn,
        "editora": publisher,
        "ano": ano,
        "categoria": ""
    }

    try:
        salvar_livro(book)  # Função que insere o livro no banco SQLite
    except Exception as e:
        logging.error("Erro ao salvar livro: " + str(e))
        return "Erro ao salvar livro.", 500

    logging.debug(f"Livro salvo: {book}")
    return redirect(url_for("listar_livros"))

# Rota para buscar livro por título nas bases de dados
@app.route("/buscar", methods=["GET", "POST"])
def buscar_livro():
    resultados = []

    if request.method == "GET" and "titulo" in request.args:
        titulo = request.args.get("titulo")

        # 1. Busca no Google Books
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
        except requests.exceptions.Timeout:
            logging.error("A requisição para o Google Books demorou muito e foi cancelada.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição para o Google Books: {e}")

        # 2. Busca na Open Library
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
        except requests.exceptions.Timeout:
            logging.error("A requisição para a Open Library demorou muito e foi cancelada.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição para a Open Library: {e}")

    return render_template("buscar_titulo.html", resultados=resultados)

# Rota para listar livros
@app.route("/livros")
@login_required
def listar_livros():
    conn = get_db_connection()
    ordenar_por = request.args.get("ordenar_por")
    titulo_busca = request.args.get("titulo", "").strip().lower()  # Obtém o título da busca

    # Busca todos os livros do banco de dados
    cursor = conn.execute("SELECT titulo, autor, isbn, editora, ano, categoria FROM livros")
    livros = [
        {
            "titulo": row[0],
            "autor": row[1],
            "isbn": row[2],
            "editora": row[3] if row[3] else "Sem editora",
            "ano": row[4] if row[4] else "Sem data",
            "categoria": row[5] if row[5] else "Sem categoria"
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()

    # Filtrar livros pelo título, se houver busca
    if titulo_busca:
        livros = [livro for livro in livros if titulo_busca in livro["titulo"].lower()]

    # Ordenação dos livros
    if ordenar_por == "titulo_asc":
        livros.sort(key=lambda x: x["titulo"])
    elif ordenar_por == "titulo_desc":
        livros.sort(key=lambda x: x["titulo"], reverse=True)
    elif ordenar_por == "ano_asc":
        livros.sort(key=lambda x: x["ano"])
    elif ordenar_por == "ano_desc":
        livros.sort(key=lambda x: x["ano"], reverse=True)

    return render_template("listar_livros.html", livros=livros, titulo_busca=titulo_busca)

# Rota para adicionar livro manualmente
@app.route("/adicionar", methods=["GET", "POST"])
@login_required
def adicionar_livro():
    if request.method == "POST":
        titulo = request.form["titulo"]
        autor = request.form["autor"]
        isbn = request.form["isbn"]
        editora = request.form["editora"]
        ano = int(request.form["ano"]) if request.form["ano"].isdigit() else 0
        categoria = request.form["categoria"]
        
        # Conectar ao banco e inserir o livro
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO livros (titulo, autor, isbn, editora, ano, categoria) VALUES (?, ?, ?, ?, ?, ?)",
            (titulo, autor, isbn, editora, ano, categoria)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("listar_livros"))
    return render_template("adicionar_livro.html")

@app.route("/adicionar_autor", methods=["GET", "POST"])
@login_required
def adicionar_autor():
    if request.method == "POST":
        nome_autor = request.form["nome_autor"]
        conn = sqlite3.connect('biblioteca.db')
        cursor = conn.cursor()

        # Inserir autor, se não existir
        cursor.execute("INSERT OR IGNORE INTO autores (nome_autor) VALUES (?)", (nome_autor,))
        conn.commit()
        conn.close()

        return redirect(url_for("listar_autores"))  # Redireciona para a lista de autores

    return render_template("adicionar_autor.html")  # Exibe o formulário para adicionar autor

# Rota para editar livro
@app.route("/editar/<isbn>", methods=["GET", "POST"])
@login_required
def editar_livro(isbn):
    conn = get_db_connection()
    livro = conn.execute("SELECT * FROM livros WHERE isbn = ?", (isbn,)).fetchone()

    if not livro:
        conn.close()
        return "Livro não encontrado", 404

    if request.method == "POST":
        titulo = request.form["titulo"]
        autor = request.form["autor"]
        editora = request.form["editora"]
        ano = int(request.form["ano"]) if request.form["ano"].isdigit() else 0
        novo_isbn = request.form["isbn"]  # ISBN pode ser alterado
        categoria = request.form["categoria"]

        conn.execute("""
            UPDATE livros 
            SET titulo = ?, autor = ?, editora = ?, ano = ?, isbn = ?, categoria = ?
            WHERE isbn = ?
        """, (titulo, autor, editora, ano, novo_isbn, categoria, isbn))
        
        conn.commit()
        conn.close()
        return redirect(url_for("listar_livros"))

    conn.close()
    return render_template("editar_livro.html", livro=livro)

# Rota para excluir livro
@app.route("/excluir/<isbn>", methods=["POST"])
def excluir_livro(isbn):
    conn = get_db_connection()
    conn.execute("DELETE FROM livros WHERE isbn = ?", (isbn,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_livros"))




# Configuração do Flask-Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Obter os dados do formulário
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()        
        if user and check_password_hash(user.password, password):
           
            # Usuário autenticado com sucesso
            login_user(user)
            
            # Redireciona para a página que o usuário tentou acessar ou para a index
            next_page = request.args.get('next')  # Captura a página inicialmente solicitada
            return redirect(url_for("index"))
        
        # Se a autenticação falhar
        return "Login inválido. Verifique o nome de usuário e a senha.", 401
    return render_template("login.html")  # Exibe o formulário de login

# Rota para registro de usuário e autenticação
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

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == "__main__":
    init_db() # Inicializa o banco de dados, criando a tabela, se necessário
    app.run(debug=True) # Inicia a aplicação Flask no modo de depuração