from flask import Flask, render_template, request, redirect, url_for
import json

app = Flask(__name__)

# Funções do sistema de catalogação
def carregar_livros():
    try:
        with open("biblioteca.json", "r") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        return []

def salvar_livros(livros):
    with open("biblioteca.json", "w") as arquivo:
        json.dump(livros, arquivo, indent=4)

def buscar_livro_por_titulo(titulo):
    livros = carregar_livros()
    return [livro for livro in livros if titulo.lower() in livro["titulo"].lower()]

# Rotas para a interface web
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/livros")
def listar_livros():
    livros = carregar_livros()
    return render_template("listar.html", livros=livros)

@app.route("/adicionar", methods=["GET", "POST"])
def adicionar_livro():
    if request.method == "POST":
        # Captura os dados do formulário
        titulo = request.form["titulo"]
        autor = request.form["autor"]
        isbn = request.form["isbn"]
        ano = request.form["ano"]

        # Adiciona o livro ao JSON
        livros = carregar_livros()
        livros.append({"titulo": titulo, "autor": autor, "isbn": isbn, "ano": ano})
        salvar_livros(livros)

        return redirect(url_for("listar_livros"))

    return render_template("adicionar.html")

@app.route("/buscar", methods=["GET", "POST"])
def buscar_livro():
    resultados = []
    if request.method == "POST":
        titulo = request.form["titulo"]
        resultados = buscar_livro_por_titulo(titulo)
    return render_template("buscar.html", resultados=resultados)

if __name__ == "__main__":
    app.run(debug=True)
