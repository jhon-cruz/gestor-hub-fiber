# Redes geográficas e busca de endereço

## Redes por localidade

Uma rede agrupa os elementos geográficos de uma área de atendimento, como **Praia Grande — SP**. Administradores podem criá-la pelo botão ao lado do seletor **Rede**.

Ao criar uma rede, há duas formas de definir seus limites:

1. selecionar uma origem KMZ, vinculando todos os elementos desse namespace e calculando os limites do desenho no PostGIS;
2. deixar a origem vazia, usando a área que está visível no mapa para uma rede ainda sem elementos.

Ao escolher uma rede, o mapa filtra os ativos, atualiza os indicadores e enquadra automaticamente seu `viewport`. A escolha fica salva somente no navegador do usuário. Ativos novos e novas importações são vinculados à rede que estiver selecionada.

Usuários `viewer` podem selecionar e consultar redes. Apenas `admin` pode criar redes, agrupar origens ou alterar a rede de um ativo.

## Tipo e quantidade de fibras

No painel de detalhes, administradores podem trocar o campo **Tipo**. Para **Cabo óptico** e **Rota planejada**, aparece o campo **Quantidade de fibras**, aceitando valores como 12, 24, 48 ou 144. O valor é salvo em `properties.fiber_count` e aparece no inventário.

O tipo escolhido manualmente é tratado como uma substituição explícita e permanece em reimportações posteriores do mesmo projeto KMZ.

## Busca de endereço

A busca aceita texto livre, por exemplo `Rua Fumio Miyazi, Boqueirão, Praia Grande, SP`. Ela é executada somente ao pressionar o botão — não existe autocomplete. Ao selecionar um resultado, o mapa enquadra o endereço e posiciona um marcador para comparação visual com a rede.

Na versão atual, a viabilidade é uma análise visual: o sistema não afirma automaticamente que um endereço é atendido. O cálculo de distância até cabos/CTOs e as regras comerciais serão um marco posterior.

O backend usa Nominatim por padrão, com:

- autenticação obrigatória;
- filtro de país para o Brasil;
- no máximo cinco resultados;
- serialização global de chamadas, respeitando ao menos um segundo entre acessos ao provedor;
- cache PostgreSQL por 30 dias, sem armazenar a consulta em texto puro;
- atribuição `© OpenStreetMap contributors`.

Configuração:

```dotenv
APP_GEOCODING_ENABLED=true
APP_GEOCODING_BASE_URL=https://nominatim.openstreetmap.org
APP_GEOCODING_CACHE_DAYS=30
```

O serviço público é adequado somente a uso interativo moderado. Produção com maior volume deve usar uma instância própria ou um provedor com SLA, mantendo a mesma interface configurável.
