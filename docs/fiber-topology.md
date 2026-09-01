# Cabos, tubos, fibras e fusões

## Estrutura relacional

A versão 0.8 introduz um domínio explícito para a estrutura interna dos cabos:

```text
OpticalCable
  ├── CableTube
  │     └── OpticalFiber
  └── MapFeature (traçado geográfico opcional)

FiberConnection
  ├── enclosure_feature_id (caixa/CTO/DIO/splitter)
  ├── FiberConnectionEndpoint A
  └── FiberConnectionEndpoint B
```

Cada cabo possui classe (`feeder`, `distribution`, `branch` ou `drop`), quantidade de tubos,
fibras por tubo, total de fibras, reserva técnica e estado operacional. A criação gera todos os
tubos e fibras na mesma transação.

## Identidade e cores

Tubos e fibras usam UUIDs próprios. Posição ou cor nunca é usada como identificador. A posição
global da fibra é única no cabo, e sua posição interna é única no tubo.

A sequência visual inicial contém doze cores e pode ser evoluída para paletas configuráveis por
operador ou fabricante. Quando há mais de doze posições, a cor recebe o número do ciclo sem perder
a identidade UUID.

## Integridade das fusões

Cada fibra possui duas extremidades lógicas: `a` e `b`. Uma conexão registra exatamente duas
extremidades de fibras diferentes. A restrição única `(fiber_id, end_side)` é mantida diretamente
no PostgreSQL, impedindo que duas requisições concorrentes ocupem a mesma extremidade.

As conexões iniciais aceitam:

- `fusion`;
- `connector`;
- `termination`.

Uma conexão precisa estar dentro de uma feição compatível: caixa de emenda, CTO, DIO ou splitter.
Criação e remoção são auditadas. Excluir uma conexão libera suas duas extremidades.

## Estados das fibras

Cada fibra aceita `available`, `reserved`, `occupied`, `damaged` ou `deactivated`. Mudanças usam
revisão otimista e são exclusivas de administradores. Usuários `viewer` podem consultar a
estrutura e as extremidades já conectadas.

## Interface

A seção **Cabos e fibras** permite:

- estruturar um traçado de cabo existente no mapa;
- gerar tubos e fibras individuais;
- consultar capacidade livre e ocupada;
- visualizar cor, tubo e posição de cada fibra;
- mudar o estado operacional da fibra;
- registrar uma fusão entre fibras dentro de uma caixa;
- retornar do cabo ao seu traçado no mapa.

## API

- `GET/POST /api/v1/optical-cables`
- `GET/PATCH /api/v1/optical-cables/{cable_id}`
- `GET /api/v1/optical-cables/{cable_id}/fibers`
- `PATCH /api/v1/optical-fibers/{fiber_id}`
- `GET/POST /api/v1/fiber-connections`
- `DELETE /api/v1/fiber-connections/{connection_id}`

## Próximas extensões

Ainda faltam conexões das fibras a portas de equipamentos/splitters, rastreamento ponta a ponta,
validação espacial dos extremos, cálculo de comprimento PostGIS e orçamento óptico acumulado.
