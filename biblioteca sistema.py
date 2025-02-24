import json

# Classe para representar um livro
class Livro:
    def __init__(self, titulo, autor, isbn, ano):
        self.titulo = titulo
        self.autor = autor
        self.isbn = isbn
        self.ano = ano

    def __repr__(self):
        return f"{self.titulo} - {self.autor} ({self.ano}) [ISBN: {self.isbn}]"

# Classe para gerenciar o catálogo
class CatalogoBiblioteca:
    def __init__(self, arquivo_dados="biblioteca.json"):
        self.arquivo_dados = arquivo_dados
        self.livros = self.carregar_dados()

    def carregar_dados(self):
        try:
            with open(self.arquivo_dados, "r") as arquivo:
                dados = json.load(arquivo)
                return [Livro(**livro) for livro in dados]
        except FileNotFoundError:
            return []

    def salvar_dados(self):
        with open(self.arquivo_dados, "w") as arquivo:
            json.dump([livro.__dict__ for livro in self.livros], arquivo, indent=4)

    def adicionar_livro(self, titulo, autor, isbn, ano):
        novo_livro = Livro(titulo, autor, isbn, ano)
        self.livros.append(novo_livro)
        self.salvar_dados()
        print(f"Livro '{titulo}' adicionado com sucesso!")

    def listar_livros(self):
        if not self.livros:
            print("Nenhum livro cadastrado.")
        else:
            for livro in self.livros:
                print(livro)

    def buscar_livro(self, criterio, valor):
        resultados = [livro for livro in self.livros if getattr(livro, criterio, "").lower() == valor.lower()]
        if resultados:
            print("Livros encontrados:")
            for livro in resultados:
                print(livro)
        else:
            print("Nenhum livro encontrado com esse critério.")

# Função principal para interagir com o sistema
def menu():
    catalogo = CatalogoBiblioteca()

    while True:
        print("\n=== Sistema de Catalogação ===")
        print("1. Adicionar livro")
        print("2. Listar livros")
        print("3. Buscar livro")
        print("4. Sair")
        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            titulo = input("Título: ")
            autor = input("Autor: ")
            isbn = input("ISBN: ")
            ano = input("Ano de publicação: ")
            catalogo.adicionar_livro(titulo, autor, isbn, ano)
        elif opcao == "2":
            catalogo.listar_livros()
        elif opcao == "3":
            criterio = input("Buscar por (titulo/autor/isbn/ano): ")
            valor = input(f"Valor para '{criterio}': ")
            catalogo.buscar_livro(criterio, valor)
        elif opcao == "4":
            print("Saindo do sistema. Até logo!")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    menu()

class Emprestimo:
    def __init__(self, usuario, livro, data_emprestimo, data_devolucao=None):
        self.usuario = usuario
        self.livro = livro
        self.data_emprestimo = data_emprestimo
        self.data_devolucao = data_devolucao

    def __repr__(self):
        status = f"Devolvido em {self.data_devolucao}" if self.data_devolucao else "Ainda não devolvido"
        return f"{self.livro.titulo} emprestado para {self.usuario} em {self.data_emprestimo} ({status})"