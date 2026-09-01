# Gestor Hub Fiber

Plataforma GIS FTTx multiusuário integrada a ERPs de provedores, derivada e interoperável com o FiberQ sem se apresentar como produto oficial do FiberQ, SGP Sistemas ou IXC Soft.

## Estado

O projeto está na fase de fundação. A primeira implementação inclui:

- API FastAPI em Ubuntu 26.04;
- interface web responsiva com mapa interativo;
- temas claro e escuro para a interface, mantendo o mapa-base claro e legível;
- redes nomeadas por localidade, com seleção e enquadramento geográfico automático;
- busca de endereços no Brasil com CEP, prioridade pela rede selecionada, cache e provedor substituível;
- inventário pesquisável com filtros por tipo e status e acesso direto ao mapa;
- PostgreSQL 18 + PostGIS 3.6;
- autenticação por login e senha com token de curta duração;
- papéis `admin` e `viewer`;
- leitura de feições para ambos os papéis;
- criação, edição e exclusão de feições somente por administradores, incluindo tipo, rede e quantidade de fibras;
- importação KMZ com pré-visualização, auditoria e reimportação sem duplicidade;
- domínio relacional e gestão visual para OLTs, DIOs, splitters, CTOs e suas portas;
- cabos estruturados com tubos, fibras individuais, estados e fusões protegidas por integridade referencial;
- ligação fibra–porta, rastreamento ponta a ponta e orçamento óptico estimado;
- ícones vetoriais distintos para CTO, caixa de emenda, splitter, OLT, DIO e ONT/ONU;
- auditoria das alterações de mapa;
- criação do primeiro administrador pela própria interface;
- FiberQ 1.4.0 preservado como submódulo upstream enquanto o fork GitHub é concluído.

## Desenvolvimento local no macOS

Requisitos: Docker Desktop e Docker Compose.

```bash
make init-env
make dev
```

A interface ficará em <http://localhost:3030>, a documentação OpenAPI em <http://localhost:3030/docs> e o PostgreSQL permanecerá acessível somente pela rede interna do Compose. No primeiro acesso, a tela inicial solicita a criação do administrador. A alternativa por terminal continua disponível com `make create-admin`.

O ambiente inicia sem credenciais externas usando OpenStreetMap/Nominatim. Para ativar Google Maps e Google Geocoding com chaves restritas, consulte [Redes geográficas e busca de endereço](docs/networks-and-address-search.md#google-maps-e-google-geocoding).

Para executar os testes:

```bash
make test
```

## Autorização

Não existe cadastro público. Somente uma instalação vazia permite criar o primeiro administrador; depois, somente administradores podem criar usuários pela interface ou por `POST /api/v1/users`. Usuários `viewer` podem autenticar e consultar o mapa, mas recebem HTTP 403 em toda operação de alteração.

## Repositórios

- Produto: <https://github.com/jhon-cruz/gestor-hub-fiber>
- Upstream FiberQ: <https://github.com/vukovicvl/fiberq>
- Fork FiberQ planejado: `https://github.com/jhon-cruz/fiberq`

Consulte [THIRD_PARTY.md](THIRD_PARTY.md) e a documentação em [docs/discovery](docs/discovery/).

Guias adicionais: [desenvolvimento local](docs/development.md), [redes e busca de endereço](docs/networks-and-address-search.md), [cabos e fibras](docs/fiber-topology.md), [importação KMZ](docs/importing-kmz.md), [domínio óptico](docs/optical-domain.md), [fork do FiberQ](docs/fiberq-fork.md) e [autenticação/RBAC](docs/security/authentication-and-roles.md).

## Licença

GPL-3.0-or-later. Consulte [LICENSE](LICENSE).
