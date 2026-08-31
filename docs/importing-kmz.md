# Importação de arquivos KMZ

## Fluxo na interface

Somente administradores visualizam **Importar KMZ** no menu lateral.

1. Selecione um arquivo `.kmz`.
2. Confirme o identificador da origem. Ele deve permanecer igual nas próximas versões do mesmo projeto.
3. Escolha o status inicial dos elementos.
4. Clique em **Analisar arquivo**.
5. Confira quantidades, tipos, novos elementos, atualizações e avisos.
6. Confirme a importação.

A prévia não altera o banco. A confirmação executa o lote em uma transação: qualquer falha reverte toda a operação.

## Mapeamento atual

| KML/KMZ | Gestor Hub Fiber |
|---|---|
| Ponto com ícone/nome CTO | `cto` |
| Ponto com ícone/nome CEO ou emenda | `splice_box` |
| Ponto OLT | `olt` |
| Ponto DIO | `dio` |
| Ponto não reconhecido | `other` |
| `LineString` | `cable` |
| `Polygon` | `area` |

Nomes, pastas, descrições, IDs, cores e larguras de linha do KML são preservados em propriedades da feição. As cores são reaplicadas no mapa quando disponíveis.

O importador não tenta deduzir status pelas cores dos ícones. O status escolhido na tela é aplicado ao lote, evitando atribuir significado não confirmado aos padrões visuais do arquivo de origem.

## Idempotência

Cada elemento é identificado pelo par:

```text
identificador da origem + ID do Placemark
```

Importar novamente exatamente o mesmo arquivo não cria registros nem revisões. Uma versão modificada com o mesmo identificador atualiza elementos com IDs conhecidos e cria apenas os IDs novos. Elementos ausentes na nova versão não são excluídos automaticamente.

## Limites e segurança

- arquivo compactado: até 20 MB;
- conteúdo descompactado: até 50 MB;
- até 100 entradas no arquivo ZIP;
- até 5.000 elementos geográficos;
- arquivos criptografados não são aceitos;
- caminhos absolutos ou com `..` são rejeitados;
- razão de compactação abusiva é rejeitada;
- entidades XML e referências externas são bloqueadas;
- geometrias devem estar dentro dos limites WGS84;
- apenas administradores podem analisar, importar e consultar o histórico.

O arquivo não é armazenado no servidor. São persistidos o hash SHA-256, nome, identificador da origem, resumo do lote, avisos e elementos convertidos para PostGIS/SRID 4326.

## Arquivo de validação

`FTTH_REDE PG ON DETALHADA.kmz` foi validado com sucesso:

- 1.006 elementos;
- 503 pontos e 503 linhas;
- 408 CTOs, 93 caixas de emenda, 1 OLT, 1 DIO e 503 cabos;
- nenhum elemento ignorado;
- nenhuma advertência do parser;
- reimportação idêntica sem duplicação.
