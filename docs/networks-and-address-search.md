# Redes geográficas e busca de endereço

## Redes por localidade

Uma rede agrupa os elementos geográficos de uma área de atendimento, como **Praia Grande — SP**. Administradores podem criá-la pelo botão ao lado do seletor **Rede**.

Ao criar uma rede, há duas formas de definir seus limites:

1. selecionar uma origem KMZ, vinculando todos os elementos desse namespace e calculando os limites do desenho no PostGIS;
2. deixar a origem vazia, usando a área que está visível no mapa para uma rede ainda sem elementos.

Ao escolher uma rede, o mapa filtra os ativos, atualiza os indicadores e enquadra automaticamente seu `viewport`. A escolha fica salva somente no navegador do usuário. Ativos novos e novas importações são vinculados à rede que estiver selecionada.

Usuários `viewer` podem selecionar e consultar redes. Apenas `admin` pode criar redes, agrupar origens ou alterar a rede de um ativo.

## Provedores cartográficos e atualização das camadas

O painel do mapa mostra o nome e a data da última planta importada. Essa data pertence aos ativos operacionais — cabos, CTOs e demais elementos do KMZ. O mapa-base é carregado sob demanda e segue o ciclo de atualização e cache do provedor selecionado; por isso não possui uma única data de versão dentro do Gestor Hub Fiber.

O sistema possui uma camada de compatibilidade para Google Maps e OpenStreetMap. Pontos, cabos, áreas, ícones, seleção de redes, enquadramento, marcador de endereço e desenho administrativo usam os mesmos dados GeoJSON/PostGIS nos dois modos.

## Tipo e quantidade de fibras

No painel de detalhes, administradores podem trocar o campo **Tipo**. Para **Cabo óptico** e **Rota planejada**, aparece o campo **Quantidade de fibras**, aceitando valores como 12, 24, 48 ou 144. O valor é salvo em `properties.fiber_count` e aparece no inventário.

O tipo escolhido manualmente é tratado como uma substituição explícita e permanece em reimportações posteriores do mesmo projeto KMZ.

## Busca de endereço

A busca aceita texto livre, por exemplo `Rua Fumio Miyazi, Boqueirão, Praia Grande, SP`, ou um CEP brasileiro. Ela é executada somente ao pressionar o botão — não existe autocomplete. Ao selecionar um resultado, o mapa enquadra o endereço e posiciona um marcador para comparação visual com a rede.

Quando uma rede está selecionada, o seu `viewport` é enviado como viés geográfico. Resultados próximos daquela área passam a ter prioridade sem impedir uma busca fora dos limites. Se o usuário informar somente a rua, cidade e estado da rede são acrescentados internamente. Consultas contendo CEP são normalizadas pelo ViaCEP antes da obtenção das coordenadas, preservando eventual número informado pelo usuário.

Na versão atual, a viabilidade é uma análise visual: o sistema não afirma automaticamente que um endereço é atendido. O cálculo de distância até cabos/CTOs e as regras comerciais serão um marco posterior.

Sem credenciais externas, o ambiente continua usando OpenStreetMap e Nominatim. O backend oferece:

- autenticação obrigatória;
- filtro de país para o Brasil;
- filtro da camada de endereços, idioma português e remoção de duplicados;
- prioridade geográfica pela rede selecionada;
- expansão opcional de CEP pelo ViaCEP;
- no máximo cinco resultados;
- serialização global de chamadas, respeitando ao menos um segundo entre acessos ao provedor;
- cache PostgreSQL por 30 dias, sem armazenar a consulta em texto puro;
- atribuição `© OpenStreetMap contributors`.

Configuração:

```dotenv
APP_GEOCODING_ENABLED=true
APP_GEOCODING_PROVIDER=nominatim
APP_GEOCODING_BASE_URL=https://nominatim.openstreetmap.org
APP_VIACEP_ENABLED=true
APP_GEOCODING_CACHE_DAYS=30
```

O serviço público é adequado somente a uso interativo moderado. Produção com maior volume deve usar uma instância própria ou um provedor com SLA. O adaptador Geoapify já está disponível:

```dotenv
APP_GEOCODING_PROVIDER=geoapify
APP_GEOCODING_BASE_URL=https://api.geoapify.com
APP_GEOCODING_API_KEY=chave-fornecida-pelo-provedor
```

A chave permanece apenas no ambiente e nunca é enviada ao navegador. A troca de provedor não exige mudança de código ou da interface.

## Google Maps e Google Geocoding

Para ativar o modo recomendado de produção, crie duas chaves distintas no Google Cloud:

1. uma chave de navegador com **Maps JavaScript API**, limitada por referenciadores HTTP aos domínios do sistema;
2. uma chave de servidor com **Geocoding API**, limitada à API e aos IPs do servidor.

Configure o `.env` sem versionar as chaves:

```dotenv
APP_MAP_PROVIDER=google
APP_GOOGLE_MAPS_BROWSER_API_KEY=chave-restrita-por-referer
APP_GEOCODING_PROVIDER=google
APP_GEOCODING_API_KEY=chave-restrita-por-ip
APP_GOOGLE_GEOCODING_BASE_URL=https://maps.googleapis.com/maps/api/geocode
APP_GEOCODING_CACHE_DAYS=30
```

A chave do navegador é entregue somente depois da autenticação, mas continua tecnicamente visível no browser, como exige a Maps JavaScript API. A proteção efetiva é a restrição por domínio e por API. A chave de geocodificação nunca é enviada ao navegador.

O sistema impede iniciar com Google Geocoding sobre um mapa não Google e limita o cache a no máximo 30 dias. A resposta normalizada preserva `location_type` (`ROOFTOP`, `RANGE_INTERPOLATED`, `GEOMETRIC_CENTER` ou `APPROXIMATE`) para que a interface informe a precisão da coordenada.

Referências: [Maps JavaScript API](https://developers.google.com/maps/documentation/javascript), [Google Geocoding API](https://developers.google.com/maps/documentation/geocoding), [preços do Google Maps Platform](https://developers.google.com/maps/billing-and-pricing/pricing), [API de busca do Nominatim](https://nominatim.org/release-docs/latest/api/Search/), [política do serviço público Nominatim](https://operations.osmfoundation.org/policies/nominatim/), [ViaCEP](https://viacep.com.br/) e [Geoapify Geocoding API](https://apidocs.geoapify.com/docs/geocoding/forward-geocoding/).
