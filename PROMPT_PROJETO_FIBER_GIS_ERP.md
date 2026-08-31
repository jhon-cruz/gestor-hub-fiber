# Prompt mestre — Plataforma GIS FTTx integrada a ERPs de provedores

Atue como arquiteto de software, desenvolvedor Python/PyQGIS e especialista em redes FTTx/GPON. Crie uma plataforma open source para planejamento, inventário e operação de redes ópticas, baseada no projeto FiberQ, com arquitetura modular para integração com ERPs de provedores. As primeiras integrações serão SGP Sistemas e IXC Soft/IXC Provedor, mas novos ERPs deverão poder ser adicionados sem alterar o núcleo do domínio.

## 1. Projeto de origem e licença

Use como upstream:

- Repositório: https://github.com/vukovicvl/fiberq
- Plugin oficial no QGIS: https://plugins.qgis.org/plugins/fiberq/
- Documentação: https://www.fiberq.net/documentation/
- Licença: GPL-3.0-or-later.

Antes de modificar código:

1. Leia integralmente `README`, `LICENSE`, documentação, estrutura do plugin, migrações, testes e modelo de dados.
2. Crie um fork próprio no GitHub, mantendo o upstream configurado para receber atualizações.
3. Preserve os avisos de copyright e cumpra integralmente a GPL-3.0-or-later.
4. Use um nome próprio para o produto derivado e não sugira que ele é uma versão oficial do FiberQ, SGP ou IXC.
5. Documente claramente quais partes vieram do FiberQ e quais foram desenvolvidas no fork.
6. Avalie tecnicamente se as integrações devem ficar em um plugin complementar, separado do núcleo FiberQ. Prefira essa separação se ela reduzir conflitos com atualizações upstream.

## 2. Objetivo do produto

Construir uma solução GIS FTTx capaz de representar e operar, no mínimo:

- POPs, sites, OLTs, chassis, slots e portas PON;
- DIOs, ODFs, bandejas, adaptadores e cordões ópticos;
- postes, caixas subterrâneas, dutos e microdutos;
- cabos feeder, distribuição, derivação e drop;
- tubos, grupos, fibras individuais e código de cores configurável;
- reservas técnicas e sobras de cabo;
- CEOs, caixas de emenda, CTOs/NAPs e caixas de terminação;
- splitters primários e secundários, razão de divisão, entrada, saídas e perdas;
- fusões, derivações, conectores e continuidade entre fibras;
- clientes, contratos, ONTs/ONUs e associação à porta da CTO;
- estados planejado, em construção, ativo, reservado, danificado e desativado;
- cálculo de distância, atenuação e orçamento óptico;
- rastreamento ponta a ponta, da porta PON ao cliente;
- capacidade livre/ocupada de cabos, splitters e CTOs;
- clientes afetados por rompimento ou falha de um elemento;
- anexos, fotografias, documentos, medições e observações de campo;
- histórico e auditoria de alterações.

## 3. Arquitetura desejada

Use uma arquitetura em camadas:

```text
QGIS + plugin GIS
        |
        v
API de integração e domínio
        |
        +---- PostgreSQL/PostGIS
        |
        +---- Conector SGP
        |
        +---- Conector IXC
        |
        +---- Futuros conectores ERP
```

Tecnologias preferenciais:

- Python e PyQGIS para o plugin;
- PostgreSQL + PostGIS como banco central multiusuário;
- GeoPackage como opção local/offline e para intercâmbio;
- FastAPI, Pydantic e SQLAlchemy/Alembic para a API/middleware;
- `httpx` ou equivalente para clientes HTTP;
- Docker Compose para ambiente local de desenvolvimento;
- OpenAPI para documentar a API própria;
- testes automatizados com `pytest`;
- lint, formatação, análise estática e CI no GitHub Actions.

Não coloque regras específicas de SGP ou IXC no domínio central. Defina uma interface semelhante a:

```python
class ERPConnector:
    def healthcheck(self): ...
    def list_customers(self, cursor=None): ...
    def get_customer(self, external_id): ...
    def list_contracts(self, cursor=None): ...
    def list_network_boxes(self, cursor=None): ...
    def get_network_box(self, external_id): ...
    def link_customer_to_port(self, customer_id, box_id, port_id): ...
    def consume_events(self, cursor=None): ...
```

Essa interface é conceitual. Ajuste-a após estudar as APIs reais, sem forçar funcionalidades que o ERP não disponibilize.

## 4. Modelo de dados e identificadores

Reutilize o `fiberq_uuid` quando aplicável e defina UUID interno estável para todas as entidades. Nunca utilize nome, coordenada ou número de porta como única chave.

Crie uma tabela genérica de referências externas contendo:

- sistema externo (`sgp`, `ixc` ou outro);
- tipo da entidade;
- UUID interno;
- ID externo;
- versão/ETag ou hash do registro;
- data da última leitura e escrita;
- cursor de sincronização;
- estado da sincronização;
- última mensagem de erro.

Inclua nos registros sincronizados, quando aplicável:

```text
erp_provider
external_customer_id
external_contract_id
external_cto_id
external_port_id
last_synced_at
sync_status
source_system
```

Modele explicitamente fibras individuais, fusões, portas de splitter e portas de CTO. Garanta integridade referencial para impedir que uma mesma porta ou fibra seja ocupada de maneira incompatível.

## 5. Estratégia de sincronização

Defina previamente a fonte de verdade:

- GIS: infraestrutura física, cabos, fibras, fusões, splitters, CTOs e portas;
- ERP: clientes, contratos, situação cadastral, plano e situação financeira;
- vínculo cliente/CTO/porta: sincronizado, com regra explícita de autoridade e resolução de conflitos.

Implemente:

- sincronização inicialmente somente de leitura;
- modo `dry-run` obrigatório para qualquer escrita;
- operações idempotentes;
- paginação e sincronização incremental;
- retries com backoff e limite;
- timeouts HTTP;
- fila de erros e reprocessamento manual;
- prevenção de registros duplicados;
- auditoria antes/depois;
- detecção e tratamento de conflitos;
- reconciliação completa programável;
- webhooks quando oficialmente suportados;
- polling incremental quando não houver webhook.

Não acesse diretamente o banco interno dos ERPs e não automatize telas HTML como solução principal. Utilize apenas APIs oficialmente suportadas.

## 6. Conector SGP Sistemas

Referências iniciais:

- Documentação para desenvolvedores: https://bookstack.sgp.net.br/books/api
- Autenticação: Token/App é o método preferencial; Basic deve existir apenas quando o endpoint exigir e com usuário de privilégio mínimo.
- Cadastro de CTO: https://wiki.sgp.net.br/wiki.php?id=cadastrar_cto

O SGP gera Token/App em `Administração -> Integrações -> Tokens`. Nunca grave token no repositório ou dentro do projeto QGIS.

Antes de implementar o conector:

1. Obtenha do suporte do SGP a documentação/Postman vigente da API Pública.
2. Confirme endpoints, filtros, paginação, autenticação e permissões para clientes, contratos, CTOs, portas, coordenadas e vínculos FTTx.
3. Confirme se existem endpoints de escrita para associação cliente/CTO/porta.
4. Confirme webhooks disponíveis e suas garantias de entrega.
5. Crie testes de contrato usando respostas sanitizadas do ambiente de homologação.

Não invente URLs ou campos ausentes na documentação. Funcionalidades não confirmadas devem ficar marcadas como `capability unavailable`.

## 7. Conector IXC Soft/IXC Provedor

Referências iniciais:

- Documentação oficial da API: https://wikiapiprovedor.ixcsoft.com.br/
- Guia oficial para token: https://wiki-erp.ixcsoft.com.br/documentacao/guias-tutoriais/api/como-gerar-um-token-para-integracoes-api
- Base normalmente utilizada: `https://SEU_DOMINIO/webservice/v1/`.

O IXC exige usuário exclusivo de integração, permissão de acesso à API, token e permissões compatíveis. Restrinja também os IPs de origem no grupo do usuário.

Antes de implementar o conector:

1. Obtenha acesso à documentação correspondente à versão do IXC do cliente.
2. Identifique tabelas/endpoints reais para clientes, contratos, caixas/CTOs, portas, coordenadas e elementos de rede.
3. Confirme formato da autenticação e cabeçalhos exigidos na instalação alvo.
4. Confirme paginação, filtros, limites, campos obrigatórios e semântica das operações de inclusão/alteração.
5. Gere fixtures sanitizadas e testes de contrato.

Não codifique nomes de tabelas ou endpoints com base apenas em exemplos encontrados na internet; valide tudo contra a documentação oficial e o ambiente de homologação.

## 8. Segurança e LGPD

Implemente obrigatoriamente:

- segredos somente em variáveis de ambiente ou cofre de segredos;
- `.env.example` sem credenciais reais;
- TLS válido em produção;
- usuários de API exclusivos e com privilégio mínimo;
- restrição por IP quando suportada;
- rotação e revogação de tokens;
- mascaramento de tokens, CPF/CNPJ, telefone e e-mail em logs;
- controle de acesso por função;
- trilha de auditoria;
- política de retenção e eliminação de dados;
- proteção contra SSRF, injeção, path traversal e exposição de arquivos;
- validação estrita de payloads externos;
- backup e restauração testados.

O plugin QGIS nunca deve receber credenciais administrativas dos ERPs. Ele deve autenticar na API intermediária, e somente o middleware deve acessar SGP/IXC.

## 9. Fases de implementação

### Fase 0 — Descoberta

- auditar o upstream FiberQ;
- documentar licença, arquitetura e modelo atual;
- obter documentação e credenciais de homologação dos ERPs;
- construir matriz de capacidades SGP versus IXC;
- registrar decisões em ADRs.

### Fase 1 — Fundação

- criar fork e configurar upstream;
- configurar ambiente reproduzível;
- criar Docker Compose com API e PostGIS;
- configurar migrations, testes e CI;
- importar um projeto FiberQ de exemplo sem perda de dados.

### Fase 2 — Domínio óptico

- complementar modelo de fibras, fusões, splitters, portas e rastreamento;
- implementar validações topológicas;
- implementar ocupação/capacidade;
- implementar orçamento óptico básico.

### Fase 3 — Framework de conectores

- definir interfaces e capacidades;
- implementar armazenamento seguro de configuração;
- criar simulador/mock de ERP;
- implementar auditoria, retries, dry-run e reconciliação.

### Fase 4 — SGP somente leitura

- importar clientes, contratos, status, coordenadas e CTO quando disponível;
- correlacionar por IDs externos;
- exibir divergências sem alterar o SGP.

### Fase 5 — IXC somente leitura

- implementar o mesmo fluxo usando a API oficial IXC;
- produzir relatório de equivalência entre os dois conectores.

### Fase 6 — Escrita controlada

- habilitar por feature flag;
- exigir dry-run e confirmação;
- iniciar por uma operação de baixo risco em homologação;
- somente depois implementar vínculo cliente/CTO/porta.

## 10. MVP obrigatório

O primeiro MVP deve permitir:

1. Criar/importar uma planta FiberQ.
2. Armazená-la em PostGIS.
3. Cadastrar OLT, porta PON, cabo, fibras, splitter, CTO e portas.
4. Traçar o caminho óptico da OLT até uma porta de CTO.
5. Conectar a um mock de ERP.
6. Conectar em modo leitura a um SGP de homologação.
7. Conectar em modo leitura a um IXC de homologação.
8. Importar clientes e contratos com coordenadas.
9. Exibir clientes no mapa e sugerir CTO próxima sem efetivar automaticamente.
10. Relatar conflitos, duplicidades e registros sem coordenadas.
11. Exportar relatório de ocupação de CTO e capacidade de splitter.

## 11. Testes e critérios de aceite

Crie testes unitários, integração e contrato. O projeto será aceito quando:

- nenhuma credencial real estiver versionada;
- a instalação local for reproduzível pela documentação;
- migrations forem reversíveis e testadas;
- uma sincronização repetida não duplicar registros;
- indisponibilidade do ERP não corromper o GIS;
- payload inválido não for persistido parcialmente;
- todos os writes puderem ser desativados globalmente;
- houver trilha de auditoria de cada alteração;
- os conectores puderem ser substituídos por mocks;
- um terceiro ERP puder ser adicionado sem alterar o núcleo;
- o código mantiver compatibilidade com a licença GPL do upstream.

## 12. Entregáveis

Entregue:

- documento de arquitetura;
- diagrama de componentes;
- diagrama entidade-relacionamento;
- matriz de capacidades SGP/IXC;
- ADRs das decisões principais;
- repositório organizado e licenciado;
- instruções de fork e atualização do upstream;
- Docker Compose de desenvolvimento;
- migrations do PostGIS;
- API OpenAPI;
- plugin QGIS instalável;
- conectores SGP e IXC;
- mocks e fixtures sanitizadas;
- suíte de testes e CI;
- manual de instalação, operação, backup e restauração;
- guia de segurança e LGPD;
- plano de evolução pós-MVP.

## 13. Forma de trabalho

Não implemente tudo de uma vez. Primeiro apresente:

1. auditoria resumida do FiberQ;
2. riscos técnicos e de licença;
3. arquitetura proposta;
4. modelo de dados inicial;
5. matriz de endpoints confirmados e ainda desconhecidos;
6. plano incremental com marcos verificáveis.

Somente comece a alterar o código depois da aprovação dessa etapa. Quando uma informação da API não estiver documentada, pare e solicite a documentação ou uma resposta sanitizada; não deduza silenciosamente o contrato da API.
