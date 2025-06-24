# Estudo da Lei Seca (Versão com Categorias e Gamificação)

Este arquivo contém o código-fonte da aplicação Flask "Estudo da Lei Seca", incluindo as funcionalidades de categorização de leis por matéria e um sistema básico de gamificação (pontos e conquistas).

## Estrutura do Projeto

- `/src`: Contém o código principal da aplicação.
  - `/models`: Define os modelos do banco de dados (User, Law, Subject, Achievement, UserProgress).
  - `/routes`: Contém os blueprints para as rotas (auth, admin, student).
  - `/static`: Arquivos estáticos (CSS, JS, imagens - se houver).
  - `/templates`: Arquivos de template HTML (Jinja2).
    - `/admin`: Templates específicos do painel de administração.
    - `/auth`: Templates de autenticação (login, signup).
    - `/student`: Templates específicos do painel do aluno.
    - `base.html`: Template base herdado por outras páginas.
  - `main.py`: Ponto de entrada da aplicação Flask, configuração e inicialização.
- `requirements.txt`: Lista de dependências Python.
- `venv/`: Ambiente virtual Python (excluído do zip, recriar se necessário).
- `README.md`: Este arquivo.

## Configuração e Execução (Desenvolvimento Local)

1.  **Criar Ambiente Virtual:**
    ```bash
    python3.11 -m venv venv
    ```
2.  **Ativar Ambiente Virtual:**
    ```bash
    source venv/bin/activate
    ```
3.  **Instalar Dependências:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configurar Banco de Dados (MySQL):**
    - Certifique-se de ter um servidor MySQL rodando.
    - Crie um banco de dados (ex: `mydb`).
    - Configure as variáveis de ambiente (ou ajuste `src/main.py`) com suas credenciais:
      - `DB_USERNAME`
      - `DB_PASSWORD`
      - `DB_HOST`
      - `DB_PORT`
      - `DB_NAME`
5.  **Executar Aplicação:**
    ```bash
    python src/main.py
    ```
    A aplicação estará disponível em `http://127.0.0.1:5001` (ou a porta configurada).



