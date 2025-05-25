# Treino Turbo - Dose de Lei Diária (Versão com Categorias e Gamificação)

Este arquivo contém o código-fonte da aplicação Flask "Treino Turbo - Dose de Lei Diária", incluindo as funcionalidades de categorização de leis por matéria e um sistema básico de gamificação (pontos e conquistas).

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

## Funcionalidades Implementadas

- Autenticação de usuários (cadastro, login, logout).
- Aprovação de usuários pelo administrador.
- Gerenciamento de Leis (CRUD) pelo administrador.
- **Gerenciamento de Matérias** pelo administrador.
- **Associação de Leis a Matérias**.
- Painel do aluno com visualização de leis.
- **Filtro de leis por matéria** no painel do aluno.
- Marcação de progresso (leis concluídas).
- Barra de progresso geral.
- Pesquisa de leis.
- Botão para "Rever Lei" (resetar progresso).
- **Sistema de Pontos:** Alunos ganham pontos ao concluir leis.
- **Estrutura de Conquistas:** Sistema pronto para adicionar e conceder conquistas (nenhuma definida por padrão).
- Interface visual com tema claro (fundo branco, detalhes roxos).

## Implantação

Esta aplicação foi implantada usando a plataforma Manus. Para implantação em outros ambientes (como Turbocloud), verifique os requisitos de suporte a Python/Flask, banco de dados MySQL e configuração de servidor web (WSGI/uWSGI).

