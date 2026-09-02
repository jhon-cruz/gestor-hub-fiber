# Plano para distribuição da integração Google Maps

## Quando executar

Este plano deve ser implementado somente quando o Gestor Hub Fiber estiver pronto para ser distribuído em instalações externas, como máquinas virtuais Ubuntu Server em Proxmox, servidores locais de provedores ou ambientes em nuvem.

Enquanto o sistema estiver em desenvolvimento, permanece válida a configuração local atual por `.env`, limitada a `localhost:3030` e `127.0.0.1:3030`.

## Problema a resolver

Não é seguro nem operacionalmente viável:

- criar chaves manualmente para cada instalação;
- distribuir a chave privada do Google Geocoding dentro das VMs dos clientes;
- depender de IP público fixo em instalações que utilizam CGNAT ou endereços dinâmicos;
- compartilhar uma chave irrestrita entre todos os clientes;
- concentrar custos sem identificar e limitar o consumo de cada instalação.

## Arquitetura escolhida

Será utilizada uma integração Google gerenciada centralmente:

```text
Navegador da instalação
   ├── Maps JavaScript API → Google Maps
   │   com chave pública restrita ao domínio da instalação
   │
   └── Busca de endereço → API local do Gestor Hub Fiber
                              └── Gateway central autenticado
                                     └── Google Geocoding API
```

Cada instalação possuirá um identificador e um token do Gestor Hub Fiber. A chave privada do Google permanecerá exclusivamente na infraestrutura central.

## Funcionamento esperado

1. O instalador registra a nova instância no serviço central.
2. A instância recebe um `installation_id` e um token revogável.
3. A instalação é vinculada a um endereço HTTPS estável, por exemplo `empresa-x.gestorhubfiber.com`.
4. O serviço central provisiona automaticamente uma chave de navegador ou inclui o domínio em uma chave restrita apropriada.
5. O navegador carrega o Google Maps diretamente, usando a chave limitada à Maps JavaScript API e ao domínio autorizado.
6. Consultas de endereço são encaminhadas pela API local ao gateway central.
7. O gateway valida a instalação, aplica limites e consulta o Google Geocoding com uma chave privada protegida por IP fixo.
8. Se o serviço Google não estiver habilitado ou disponível, a instalação utiliza o provedor cartográfico alternativo configurado.

## Requisitos de domínio e rede

- Cada instalação deve possuir um hostname estável, mesmo quando a VM estiver em rede privada.
- O hostname pode resolver internamente para um endereço RFC 1918 usando DNS local ou dividido.
- O acesso deve utilizar HTTPS com certificado válido.
- A VM não precisa ter IP público fixo nem receber conexões diretamente da internet.
- A VM e os navegadores precisam de acesso HTTPS de saída ao gateway e aos domínios necessários do Google Maps.
- Instalações totalmente offline devem utilizar OpenStreetMap ou outro provedor compatível com operação offline; Google Maps não funciona sem internet.

## Credenciais

### Chave do navegador

- limitada à Maps JavaScript API;
- restrita ao domínio HTTPS da instalação;
- provisionada automaticamente, sem intervenção do cliente;
- separada entre desenvolvimento, homologação e produção;
- passível de rotação e revogação centralizadas;
- protegida adicionalmente com Firebase App Check quando aplicável.

### Chave do servidor

- limitada à Geocoding API;
- armazenada somente no gateway central;
- protegida por gerenciador de segredos;
- restrita ao IP público fixo do gateway;
- nunca incluída em imagem Docker, instalador, repositório, resposta da API ou arquivo `.env` do cliente.

### Token da instalação

- identifica a instalação, não concede acesso direto ao Google;
- possui expiração ou rotação controlada;
- pode ser revogado sem alterar outras instalações;
- é armazenado como segredo no servidor Ubuntu;
- acompanha todas as chamadas feitas ao gateway.

## Controle de consumo e custos

O gateway deverá implementar:

- contador de utilização por instalação;
- limite de requisições por minuto;
- limite mensal por plano ou contrato;
- proteção contra repetição e automação abusiva;
- alertas de orçamento e anomalias;
- bloqueio individual sem interromper outros clientes;
- painel administrativo de consumo;
- registros sem armazenar desnecessariamente endereços pesquisados;
- cache apenas dentro dos limites permitidos pelos termos do Google.

Todo consumo feito com as credenciais do produto será de responsabilidade da conta de faturamento associada. Os preços e franquias devem ser conferidos novamente antes do lançamento.

## Alterações futuras no Gestor Hub Fiber

- adicionar `installation_id`, estado de ativação e token da instalação;
- criar tela/CLI de ativação da instância;
- substituir a chave privada local de Geocoding pela URL do gateway;
- obter a configuração pública do mapa pelo serviço de controle;
- adicionar renovação, rotação e revogação de credenciais;
- registrar métricas de consumo sem incluir a chave Google nos logs;
- implementar fallback automático e indicação visual do provedor ativo;
- adicionar diagnóstico de DNS, HTTPS e conectividade ao instalador;
- manter um modo `BYOK` opcional para clientes que desejarem usar sua própria conta Google Cloud.

## Etapas de implementação

### Etapa 1 — Controle de instalações

- serviço central de cadastro;
- geração e revogação de tokens;
- associação entre instalação, cliente e domínio;
- auditoria de ativação.

### Etapa 2 — Gateway de geocodificação

- endpoint autenticado e com contrato restrito;
- validação e normalização das consultas;
- limites por instalação;
- chave Google armazenada em cofre de segredos;
- métricas, alertas e bloqueio de abuso.

### Etapa 3 — Provisionamento do mapa no navegador

- automação via Google Cloud/API Keys API;
- restrição da chave ao domínio cadastrado;
- separação entre ambientes;
- rotação sem reinstalar o sistema;
- avaliação e ativação do App Check.

### Etapa 4 — Instalador de produção

- solicitação do token de ativação;
- validação do hostname e HTTPS;
- teste de conectividade;
- configuração automática do provedor;
- opção de fallback e modo `BYOK`.

### Etapa 5 — Operação comercial

- limites por plano;
- painel de consumo e custos;
- política de uso aceitável;
- termos e política de privacidade com avisos exigidos pelo Google;
- processo de suporte, suspensão e rotação de credenciais.

## Critérios de aceite

- nenhuma chave privada Google existe nas instalações distribuídas;
- o cliente não precisa acessar o Google Cloud para uma instalação gerenciada;
- uma credencial comprometida pode ser bloqueada sem afetar outros clientes;
- o domínio e a instalação são validados antes de liberar o Google Maps;
- cada instalação possui métricas e limites próprios;
- uma VM atrás de CGNAT consegue pesquisar endereços usando somente conexão de saída;
- a indisponibilidade do gateway não impede o acesso aos dados ópticos locais;
- o fallback cartográfico funciona e informa claramente o provedor ativo;
- a aplicação mantém atribuições, termos e avisos exigidos pelo Google.

## Referências oficiais para revisar antes da implementação

- [Google Maps Platform — práticas de segurança para chaves](https://developers.google.com/maps/api-security-best-practices)
- [Google Maps Platform — preços e faturamento](https://developers.google.com/maps/billing-and-pricing/pay-as-you-go)
- [Google Maps Platform — termos de serviço](https://cloud.google.com/maps-platform/terms)
- [Maps JavaScript API — Firebase App Check](https://developers.google.com/maps/documentation/javascript/maps-app-check)

As condições comerciais, limites, produtos e práticas recomendadas podem mudar. Todas as referências devem ser revisadas novamente na data em que a distribuição for iniciada.
