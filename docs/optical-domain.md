# Domínio óptico — equipamentos e portas

Esta primeira entrega da Fase 2 introduz entidades relacionais para equipamentos e portas. Ela
complementa as feições geográficas: o ponto no mapa representa a localização, enquanto o
equipamento óptico representa capacidade, fabricante, modelo, estado e portas físicas.

## Equipamentos suportados

- `olt`: cria portas do tipo `pon`;
- `dio`: cria portas do tipo `adapter`;
- `cto`: cria portas do tipo `cto_distribution`;
- `splitter`: cria uma `splitter_input` e a quantidade configurada de `splitter_output`.

Cada equipamento pode ser vinculado a uma única `map_feature` de tipo compatível. Um elemento
geográfico também só pode representar um equipamento óptico. O vínculo usa UUID e nunca depende
do nome ou das coordenadas.

## Estados das portas

As portas aceitam `available`, `reserved`, `occupied`, `damaged` e `deactivated`. A posição é
única dentro da combinação equipamento/tipo de porta. Alterações exigem a revisão atual, evitando
que dois operadores sobrescrevam silenciosamente o mesmo registro.

## API

Leitura é permitida para `admin` e `viewer`; criação e alteração exigem `admin`.

- `GET /api/v1/optical-devices`
- `POST /api/v1/optical-devices`
- `GET /api/v1/optical-devices/{device_id}`
- `PATCH /api/v1/optical-devices/{device_id}`
- `GET /api/v1/optical-devices/{device_id}/ports`
- `PATCH /api/v1/optical-ports/{port_id}`

A criação do equipamento e de todas as portas acontece na mesma transação. Quando vinculado ao
mapa, o total de portas é refletido na propriedade `capacity` da feição. Todas as alterações são
auditadas.

## Interface

A seção **Equipamentos** oferece pesquisa, filtro por tipo e indicadores de capacidade instalada,
ocupada e disponível. Usuários `viewer` podem consultar equipamentos e portas. Administradores
também podem:

- criar equipamentos e gerar sua capacidade de portas em uma transação;
- vincular o equipamento a uma feição compatível do mapa;
- editar identificação, fabricante, modelo, série e estado operacional;
- alterar cada porta entre disponível, reservada, ocupada, danificada ou desativada;
- navegar do equipamento para seu item geográfico.

## Evolução e limites

Fibras individuais e fusões passaram a ser entidades relacionais na migration `0005`, conforme
[cabos e fibras](fiber-topology.md). Ainda faltam as conexões entre fibras e portas de equipamentos,
além do rastreamento e orçamento óptico ponta a ponta. A conectividade continuará fora do JSON
genérico da feição geográfica.
