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

## Nominatim

- Projeto: Nominatim / OpenStreetMap
- Documentação: <https://nominatim.org/release-docs/latest/api/Search/>
- Política pública: <https://operations.osmfoundation.org/policies/nominatim/>
- Uso: geocodificação de buscas iniciadas explicitamente pelo usuário, limitada a resultados brasileiros.

## Google Maps Platform (opcional)

- Produto: Maps JavaScript API e Geocoding API
- Site: <https://mapsplatform.google.com/>
- Termos: <https://cloud.google.com/maps-platform/terms>
- Uso: mapa-base e busca de endereços quando habilitados pelo operador com credenciais próprias.
- Observação: serviço proprietário externo, sujeito aos termos, limites e preços da conta Google Cloud do operador; não é redistribuído como parte do código GPL.

A aplicação não implementa autocomplete, limita as chamadas ao provedor público a no máximo uma por segundo, usa identificação própria, mantém cache local e exibe atribuição. Uma implantação com volume elevado deve configurar um serviço próprio ou provedor contratado.

## defusedxml

- Projeto: defusedxml
- Versão: `0.7.1`
- Site: <https://pypi.org/project/defusedxml/>
- Licença: Python Software Foundation License
- Uso: análise defensiva do XML contido em arquivos KMZ/KML.
