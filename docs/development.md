# Ambiente de desenvolvimento

## Arquitetura local

O macOS executa Docker Desktop. A API roda em um container `linux/amd64` baseado em Ubuntu 26.04 LTS; PostGIS roda em um container separado e não publica porta no host.

```text
macOS
  └─ Docker Desktop (Linux/amd64)
       ├─ api       Ubuntu 26.04 / Python 3.14 / porta local 3030
       ├─ migration Ubuntu 26.04 / Alembic
       └─ db        PostgreSQL 18 / PostGIS 3.6 / rede interna do Compose
```

Um container compartilha o userspace do Ubuntu, não inicializa outro kernel como uma máquina virtual. Para validar kernel, systemd, firewall e operação real, continuaremos usando um Ubuntu Server 26.04 de homologação além deste ambiente local.

## Primeiro start

```bash
make init-env
make dev
make status
curl http://localhost:3030/health
```

Interfaces disponíveis:

- Interface web: <http://localhost:3030>
- OpenAPI: <http://localhost:3030/docs>
- Healthcheck: <http://localhost:3030/health>
- Readiness: <http://localhost:3030/ready>

## Primeiro administrador

Abra <http://localhost:3030> e preencha o formulário de primeiro acesso. Esse formulário só é aceito enquanto o banco não possui nenhuma conta. Como alternativa administrativa local:

```bash
make create-admin
```

A senha é lida sem eco e armazenada somente como hash Argon2. Não passe senhas na linha de comando, em commits ou em arquivos de documentação.

## Testes

```bash
make test
```

Os testes usam o banco separado `gestor_hub_fiber_test`; nunca limpam contas ou mapas do banco de desenvolvimento. Para inspecionar logs:

```bash
make logs
```

## Parada

```bash
make stop
```

O volume PostgreSQL é preservado. Para remover também o banco local descartável, use conscientemente `docker compose down --volumes`.

## Portas

- `3030/tcp`: API, vinculada a `127.0.0.1`.
- `5432/tcp`: somente dentro da rede Docker; não publicada no macOS.
- Porta 3000 não é usada.
