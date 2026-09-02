# Plano do diagrama de fusões

## Objetivo

Permitir que qualquer operador identifique, sem interpretar tabelas técnicas extensas:

- quais fibras chegam e saem de uma CEO (caixa de emenda óptica);
- quais fibras estão livres, reservadas, fusionadas, danificadas ou inativas;
- para onde cada fusão segue;
- quais portas estão livres ou ocupadas em CTOs, splitters, DIOs e OLTs;
- se existe continuidade e margem óptica até o destino.

## Linguagem visual

O diagrama usará texto, símbolo e cor simultaneamente para não depender apenas da percepção de cores.

| Estado | Cor | Símbolo | Texto exibido |
|---|---|---|---|
| Livre | verde | ○ | Livre |
| Conectada/fusionada | azul | ●—● | Conectada |
| Reservada | amarelo | ◐ | Reservada |
| Danificada | vermelho | × | Danificada |
| Inativa | cinza | — | Inativa |

As cores normalizadas dos 12 padrões de fibra continuam visíveis numa faixa lateral, separadas da cor operacional do estado.

## Tela principal

Ao abrir **Diagrama óptico**, o usuário verá:

1. seletor de rede e busca por CEO, CTO, cabo ou equipamento;
2. cartões com totais de fibras livres, ocupadas, reservadas e danificadas;
3. lista de CEOs e CTOs com uma barra de ocupação (`18/24 ocupadas`);
4. filtros rápidos: `Somente livres`, `Somente com falha`, `Com capacidade disponível`;
5. botão **Abrir diagrama** em cada caixa/equipamento.

## Diagrama de uma CEO

O desenho será organizado da esquerda para a direita:

```text
CABOS DE ENTRADA       BANDEJA / FUSÕES                 CABOS DE SAÍDA
Feeder 48FO            Fibra 01 azul  ●────●            Distribuição 24FO
  01 azul  ●────────── [Fusão F-018] ─────────────────►  01 azul  ●
  02 laranja ○         Livre                             02 laranja ○
  03 verde  ×───────── [Falha registrada]                03 verde  —
```

Cada linha representa uma fibra. Ao passar o cursor ou tocar na linha, o sistema mostra cabo, tubo, posição, extremidade A/B, destino, perda da fusão e observações. Linhas livres permanecem visíveis e podem ser ocultadas por filtro.

Para caixas grandes, as fibras serão agrupadas por cabo e tubo, com grupos recolhíveis de 12 fibras. O cabeçalho da CEO mostrará `livres / total`, ocupação percentual e alertas.

## Visão de CTOs e portas

A CTO terá uma matriz de portas numeradas, semelhante a um painel físico:

```text
CTO-014 · 16 portas · 11 ocupadas · 5 livres
[01 ● Ocupada] [02 ○ Livre] [03 ● Ocupada] [04 ◐ Reservada]
[05 ○ Livre  ] [06 × Falha] [07 ● Ocupada] [08 ○ Livre    ]
```

Ao selecionar uma porta ocupada, o sistema destaca o caminho de origem até a porta. Uma porta livre mostra imediatamente se há fibra disponível chegando à CTO; assim, “porta livre sem fibra disponível” não será confundida com viabilidade real.

## Navegação e rastreamento

- Um clique em uma fusão destaca somente o caminho relacionado.
- **Rastrear até a origem** percorre CTO → splitter → CEO → DIO → OLT.
- **Rastrear até o cliente/destino** percorre o sentido oposto.
- Cada trecho mostra perda individual, perda acumulada e margem óptica.
- Um atalho **Ver no mapa** centraliza o ativo geográfico correspondente.
- O diagrama será somente leitura para `viewer`; alterações continuarão exclusivas de `admin`.

## Dados necessários

O núcleo atual já possui fibras, extremidades A/B, fusões, ligações fibra–porta e rastreamento. Para o diagrama serão acrescentados:

- bandejas da CEO e capacidade por bandeja;
- posição física da fusão na bandeja;
- relacionamento explícito entre splitter, porta de entrada e portas de saída;
- estado calculado de disponibilidade (`porta livre` + `fibra de alimentação disponível`);
- coordenadas de layout do diagrama geradas na consulta, sem gravar posições visuais como regra de negócio.

## Etapas de implementação

### Etapa 1 — Consulta operacional

- endpoint resumido de ocupação por CEO/CTO/equipamento;
- filtros por rede, tipo, disponibilidade e falha;
- testes dos cálculos de livre/ocupada/reservada/danificada.

### Etapa 2 — Diagrama de CEO

- cabos e tubos agrupados nas laterais;
- fusões no centro, uma linha por fibra;
- detalhes por clique e filtros de densidade;
- suporte inicial a até 288 fibras sem perda de legibilidade.

### Etapa 3 — Painel de CTO e splitter

- matriz visual de portas;
- distinção entre porta livre com e sem fibra disponível;
- rastreamento da porta selecionada até OLT/CEO.

### Etapa 4 — Edição assistida

- criar/desfazer fusões pelo diagrama;
- reservar/liberar fibras e portas;
- validação antes de salvar e confirmação da operação;
- histórico de auditoria acessível no próprio diagrama.

## Critérios de aceite

- O estado de uma fibra ou porta deve ser entendido em até três segundos sem abrir outra tela.
- Toda cor deve possuir também símbolo e texto.
- O total livre + reservado + ocupado + danificado + inativo deve coincidir com a capacidade cadastrada.
- Uma porta só pode aparecer como **viável** quando estiver livre e houver continuidade óptica disponível até ela.
- Nenhuma fusão pode utilizar duas vezes a mesma extremidade de fibra.
- `viewer` não pode alterar fusões, fibras ou portas.
- O diagrama deve permanecer utilizável em notebook e tablet e suportar navegação por teclado.
