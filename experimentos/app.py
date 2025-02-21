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

def salvar_livros(livros):
    with open("biblioteca.json", "w", encoding="utf-8") as arquivo:
        json.dump(livros, arquivo, indent=4, ensure_ascii=False)

def buscar_livro_por_titulo(titulo):
    livros = carregar_livros()
    return [livro for livro in livros if titulo.lower() in livro["titulo"].lower()]

# Rota principal com busca por ISBN
@app.route("/", methods=["GET", "POST"])
def index():
    book_info = None
    if request.method == "POST":
        isbn = request.form.get("isbn")
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get("totalItems", 0) > 0:
                book_info = data["items"][0]["volumeInfo"]
                book_info["isbn"] = isbn
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

# Rota para listar livros
@app.route("/livros")
def listar_livros():
    livros = carregar_livros()
    ordenar_por = request.args.get("ordenar_por")

    if ordenar_por == "titulo_asc":
        livros.sort(key=lambda x: x["titulo"])
    elif ordenar_por == "titulo_desc":
        livros.sort(key=lambda x: x["titulo"], reverse=True)
    elif ordenar_por == "ano_asc":
        livros.sort(key=lambda x: x["ano"])
    elif ordenar_por == "ano_desc":
        livros.sort(key=lambda x: x["ano"], reverse=True)

    return render_template("listar_livros.html", livros=livros)

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

# Rota para buscar livro por título
@app.route("/buscar", methods=["GET", "POST"])
def buscar_livro():
    resultados = []
    if request.method == "POST":
        titulo = request.form["titulo"]
        resultados = buscar_livro_por_titulo(titulo)
    return render_template("buscar.html", resultados=resultados)

@app.route("/excluir/<isbn>", methods=["POST"])
def excluir_livro(isbn):
    livros = carregar_livros()
    livros = [livro for livro in livros if livro["isbn"] != isbn]
    salvar_livros(livros)
    return redirect(url_for("listar_livros"))

if __name__ == "__main__":
    app.run(debug=True)
