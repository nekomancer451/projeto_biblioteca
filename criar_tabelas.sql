-- Tabela para autores
CREATE TABLE IF NOT EXISTS autores (
    id_autor INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_autor TEXT NOT NULL UNIQUE
);

-- Tabela para categorias
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_categoria TEXT NOT NULL UNIQUE
);

-- Tabela para livros
CREATE TABLE IF NOT EXISTS livros (
    id_livro INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    isbn TEXT NOT NULL UNIQUE,
    id_autor INTEGER,
    id_editora INTEGER,
    id_categoria INTEGER,
    ano INTEGER,
    FOREIGN KEY(id_autor) REFERENCES autores(id_autor),
    FOREIGN KEY(id_categoria) REFERENCES categorias(id_categoria)
);
