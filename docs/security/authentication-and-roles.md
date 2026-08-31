# Autenticação e níveis de autorização

## Papéis iniciais

| Papel | Ler mapa | Criar/editar/excluir mapa | Criar usuários | Listar usuários |
|---|---:|---:|---:|---:|
| `admin` | Sim | Sim | Sim | Sim |
| `viewer` | Sim | Não | Não | Não |

As verificações são feitas no servidor em cada requisição. Ocultar botões na interface não substitui a autorização da API.

## Contas

- Não existe autocadastro público.
- Em uma instalação vazia, a interface permite criar exatamente o primeiro administrador. Um bloqueio transacional no PostgreSQL evita dois bootstraps simultâneos; depois disso, o endpoint responde HTTP 409.
- A CLI local `make create-admin` permanece disponível como alternativa operacional.
- Novas contas são criadas por administradores pela interface ou em `POST /api/v1/users`.
- Senhas exigem no mínimo 12 caracteres e são armazenadas com Argon2.
- Tokens JWT usam HS256, expiração curta e segredo fornecido por variável de ambiente.
- O papel presente no token não é usado isoladamente: a API relê o usuário ativo no banco.

## Alterações de mapa

`POST`, `PATCH` e `DELETE` em `/api/v1/map-features` exigem `admin`. Atualizações exigem `expected_revision`; uma edição concorrente com revisão antiga recebe HTTP 409.

Cada alteração gera um registro de auditoria na mesma transação, contendo ator, ação, entidade e estado anterior/posterior aplicável.

## Evolução prevista

- refresh tokens rotativos ou sessão federada;
- revogação e encerramento de sessões;
- alteração obrigatória de senha inicial;
- política configurável de senha e MFA para administradores;
- escopos adicionais por região/projeto;
- auditoria consultável apenas por papel específico;
- rate limiting no endpoint de login.
