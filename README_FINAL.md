# Treino Turbo - Dose de Lei Diária (Versão Final com Correção)

Este documento descreve a versão final do projeto "Treino Turbo - Dose de Lei Diária", incluindo todas as funcionalidades implementadas e a correção para o bug de exclusão de leis.

## Funcionalidades Implementadas

1.  **Gerenciamento de Leis e Matérias (Admin):**
    *   Adicionar, editar e excluir leis (título, descrição, conteúdo, matéria).
    *   **Correção:** A exclusão de leis agora remove corretamente os registros de progresso associados, evitando erros.
    *   Adicionar, editar e excluir matérias (categorias para as leis).

2.  **Visualização e Progresso (Aluno):**
    *   Listar leis disponíveis, com opção de filtrar por matéria e buscar por título/descrição.
    *   Visualizar o conteúdo completo de cada lei.
    *   **Controle de Status:** O progresso de cada lei é gerenciado por um campo de status (
'nao_iniciado
', 
'em_andamento
', 
'concluido
').
    *   Marcar leis como concluídas (muda status para 
'concluido
').
    *   Marcar leis como "Rever" (muda status para 
'em_andamento
').

3.  **Gamificação:**
    *   **Pontos:** Ganhar 10 pontos ao marcar uma lei como concluída pela primeira vez.
    *   **Conquistas:** Desbloquear conquistas automaticamente com base no número total de leis concluídas (5, 10, 20, 30, 50, 75, 100, 150, 200 leis).
    *   **Visualização:** Pontos e conquistas são exibidos no painel do aluno.

4.  **Rastreamento de Artigos:**
    *   Salvar e exibir o último artigo lido para cada lei.
    *   Salvar a posição pela primeira vez muda o status para 
'em_andamento
'.
    *   Limpar o artigo reverte o status para 
'nao_iniciado
' (se estava 
'em_andamento
').

5.  **Mural de Avisos:**
    *   Gerenciamento (Admin): Criar, editar, ativar/desativar e excluir avisos.
    *   Exibição (Aluno): Avisos ativos são exibidos no painel do aluno.

6.  **Informações de Contato:**
    *   Dados de contato exibidos no rodapé.

## Instruções para Execução Local / Implantação

Este projeto é uma aplicação web Flask.

**Pré-requisitos:**
*   Python 3.11 ou superior
*   `pip` (gerenciador de pacotes Python)
*   (Opcional) Um servidor de banco de dados MySQL se você quiser usar um banco de dados persistente em produção (para execução local, ele usará um banco de dados SQLite por padrão, que é criado automaticamente).

**Passos para Execução Local:**

1.  **Descompacte o arquivo zip:** Extraia o conteúdo do arquivo `treino_turbo_final_v8_com_correcao_exclusao.zip` para uma pasta no seu computador.
2.  **Navegue até a pasta do projeto:** Abra um terminal ou prompt de comando e use o comando `cd` para entrar na pasta que você acabou de criar (a pasta que contém o diretório `src`, `venv`, `requirements.txt`, etc.).
3.  **Ative o Ambiente Virtual:**
    *   No Linux/macOS: `source venv/bin/activate`
    *   No Windows: `venv\Scripts\activate`
4.  **Instale as Dependências:** Com o ambiente virtual ativado, execute: `pip install -r requirements.txt`
5.  **Execute a Aplicação:** Ainda no terminal com o ambiente virtual ativo, execute: `python src/main.py`
6.  **Acesse no Navegador:** Abra seu navegador e acesse `http://127.0.0.1:5000` ou `http://localhost:5000`.

**Observações para Implantação:**

*   **Banco de Dados:** Para produção, você provavelmente vai querer usar um banco de dados mais robusto como MySQL ou PostgreSQL. Você precisará:
    *   Instalar o driver apropriado (ex: `PyMySQL` já está em `requirements.txt`).
    *   Configurar a string de conexão `SQLALCHEMY_DATABASE_URI` no arquivo `src/main.py`, descomentando a linha relevante e ajustando as credenciais (usuário, senha, host, nome do banco) de acordo com seu servidor de banco de dados. Geralmente, essas credenciais são passadas por variáveis de ambiente no servidor de produção.
    *   Garantir que o servidor de banco de dados esteja acessível pela aplicação.
*   **Servidor WSGI:** Em produção, não use o servidor de desenvolvimento do Flask (`flask run` ou `python src/main.py`). Use um servidor WSGI como Gunicorn ou uWSGI por trás de um servidor web como Nginx ou Apache.
    *   Exemplo com Gunicorn: `gunicorn --bind 0.0.0.0:5000 "src.main:app"` (ajuste a porta conforme necessário).
*   **Variáveis de Ambiente:** Configure a `SECRET_KEY` e as credenciais do banco de dados usando variáveis de ambiente no seu servidor de implantação por segurança.
*   **Modo Debug:** Certifique-se de que `debug=True` **não** esteja ativo em produção (remova ou defina como `False` na chamada `app.run` ou confie no servidor WSGI).

## Arquivos do Projeto

O arquivo zip anexo (`treino_turbo_final_v8_com_correcao_exclusao.zip`) contém o código-fonte completo desta versão do projeto.

