# Proveniência e componentes de terceiros

## FiberQ

- Projeto: FiberQ
- Autor/mantenedor upstream: Vladimir Vukovic
- Repositório: <https://github.com/vukovicvl/fiberq>
- Versão inicialmente fixada: `v1.4.0`
- Commit: `07b8c12a628a5cc9641569ba3f8ca9ef867ce696`
- Licença: GPL-3.0-or-later
- Local: `vendor/fiberq` (submódulo Git)

O Gestor Hub Fiber é um produto derivado independente. Não é uma versão oficial e não possui afiliação ou endosso do FiberQ, SGP Sistemas ou IXC Soft.

As alterações próprias devem ficar fora do submódulo sempre que possível. Alterações indispensáveis ao FiberQ serão feitas no fork, identificadas por commit e data, preservando os avisos de copyright e a licença GPL-3.0-or-later.

## Leaflet

- Projeto: Leaflet
- Versão: `1.9.4`
- Site: <https://leafletjs.com/>
- Licença: BSD-2-Clause
- Uso: biblioteca do mapa interativo, carregada pelo CDN recomendado na documentação oficial com verificação SRI.

## OpenStreetMap

- Projeto: OpenStreetMap
- Site: <https://www.openstreetmap.org/>
- Uso atual: mapa-base para desenvolvimento, com atribuição visível no mapa.
- Política de tiles: <https://operations.osmfoundation.org/policies/tiles/>

Os tiles públicos são adequados somente ao desenvolvimento e uso interativo moderado, sem download em massa. Antes de produção será definido um provedor com SLA ou uma infraestrutura própria.
