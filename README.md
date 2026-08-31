# Gestor Hub Fiber

Plataforma GIS FTTx multiusuário integrada a ERPs de provedores, derivada e interoperável com o FiberQ sem se apresentar como produto oficial do FiberQ, SGP Sistemas ou IXC Soft.

## Estado

O projeto está na fase de fundação. A primeira implementação inclui:

- API FastAPI em Ubuntu 26.04;
- PostgreSQL 18 + PostGIS 3.6;
- autenticação por login e senha com token de curta duração;
- papéis `admin` e `viewer`;
- leitura de feições para ambos os papéis;
- criação, edição e exclusão de feições somente por administradores;
- auditoria das alterações de mapa;
- FiberQ 1.4.0 preservado como submódulo upstream enquanto o fork GitHub é concluído.

## Desenvolvimento local no macOS

Requisitos: Docker Desktop e Docker Compose.

```bash
make init-env
make dev
make create-admin
```

A API ficará em <http://localhost:3030>, a documentação OpenAPI em <http://localhost:3030/docs> e o PostgreSQL permanecerá acessível somente pela rede interna do Compose.

Para executar os testes:

```bash
make test
```

## Autorização

Não existe cadastro público. O primeiro administrador é criado pela CLI; depois, somente administradores podem criar usuários por `POST /api/v1/users`. Usuários `viewer` podem autenticar e consultar o mapa, mas recebem HTTP 403 em toda operação de alteração.

## Repositórios

- Produto: <https://github.com/jhon-cruz/gestor-hub-fiber>
- Upstream FiberQ: <https://github.com/vukovicvl/fiberq>
- Fork FiberQ planejado: `https://github.com/jhon-cruz/fiberq`

Consulte [THIRD_PARTY.md](THIRD_PARTY.md) e a documentação em [docs/discovery](docs/discovery/).

Guias adicionais: [desenvolvimento local](docs/development.md), [fork do FiberQ](docs/fiberq-fork.md) e [autenticação/RBAC](docs/security/authentication-and-roles.md).

## Licença

GPL-3.0-or-later. Consulte [LICENSE](LICENSE).
