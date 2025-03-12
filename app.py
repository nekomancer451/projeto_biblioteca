from flask import Flask, render_template, request, redirect, url_for
import requests
import json
import logging

app = Flask(__name__)

# Configuração do logging
logging.basicConfig(level=logging.DEBUG)

# Funções para carregar e salvar livros no arquivo JSON
def carregar_livros():
    try:
        with open("biblioteca.json", "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        return []

# Função para salvar livros no arquivo JSON
def salvar_livros(livros):
    with open("biblioteca.json", "w", encoding="utf-8") as arquivo:
        json.dump(livros, arquivo, indent=4, ensure_ascii=False)

# Função para buscar livro por título
def buscar_livro_por_titulo(titulo):
    livros = carregar_livros()
    return [livro for livro in livros if titulo.lower() in livro["titulo"].lower()]

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
def save_book():
    title = request.form.get("title")
    authors = request.form.get("authors")
    publisher = request.form.get("publisher")
    published_date = request.form.get("published_date")
    isbn = request.form.get("isbn")

    # Verifica se o ISBN já existe na lista de livros
    livros = carregar_livros()
    if any(livro['isbn'] == isbn for livro in livros):
        return "Este livro já está na base de dados.", 400  # Retorna um erro 400 se o livro já existir

    # Extrai o ano da data de publicação (caso esteja no formato "YYYY" ou "YYYY-MM-DD")
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

    livros.append(book)
    salvar_livros(livros)

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
def listar_livros():
    livros = carregar_livros()
    ordenar_por = request.args.get("ordenar_por")
    titulo_busca = request.args.get("titulo", "").strip().lower()  # Obtém o título da busca

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
def adicionar_livro():
    if request.method == "POST":
        titulo = request.form["titulo"]
        autor = request.form["autor"]
        isbn = request.form["isbn"]
        editora = request.form["editora"]
        ano = request.form["ano"]
        categoria = request.form["categoria"]
        livros = carregar_livros()
        livros.append({
            "titulo": titulo,
            "autor": autor,
            "isbn": isbn,
            "editora": editora,
            "ano": int(ano) if ano.isdigit() else 0,
            "categoria": categoria
        })
        salvar_livros(livros)
        return redirect(url_for("listar_livros"))
    return render_template("adicionar_livro.html")

@app.route("/editar/<isbn>", methods=["GET", "POST"])
def editar_livro(isbn):
    livros = carregar_livros()
    livro = next((livro for livro in livros if livro["isbn"] == isbn), None)
    
    if not livro:
        return "Livro não encontrado", 404

    if request.method == "POST":
        livro["titulo"] = request.form["titulo"]
        livro["autor"] = request.form["autor"]
        livro["editora"] = request.form["editora"]
        livro["ano"] = int(request.form["ano"]) if request.form["ano"].isdigit() else 0
        livro["isbn"] = request.form["isbn"]  # Não converta para int!
        livro["categoria"] = request.form["categoria"]
        salvar_livros(livros)
        return redirect(url_for("listar_livros"))

    return render_template("editar_livro.html", livro=livro)

@app.route("/excluir/<isbn>", methods=["POST"])
def excluir_livro(isbn):
    livros = carregar_livros()
    livros = [livro for livro in livros if livro["isbn"] != isbn]
    salvar_livros(livros)
    return redirect(url_for("listar_livros"))

if __name__ == "__main__":
    app.run(debug=True)