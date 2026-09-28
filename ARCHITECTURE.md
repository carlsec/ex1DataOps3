# Architecture Decision

Todas as evidências abaixo vêm de execuções reais do gate neste repositório, com o instante de referência fixo usado no CI:

```bash
python -m src.quality_gate --input data/input/sample_dirty.csv --reference-datetime 2026-09-13T12:00:00
```

Resumo do `quality_report.json` gerado para o dado sujo:

```json
{
  "row_count": 9,
  "blocking_failures": ["nulls", "duplicates", "freshness", "consistency"],
  "warning_failures": ["volume"],
  "passed": false
}
```

O dado limpo (`sample_clean.csv`, 30 linhas) passa em todos os seis checks e o gate retorna exit code 0.

## 1. Quais checks vocês marcaram como BLOQUEANTES e por quê?

Mantivemos o `SEVERITY` de `src/dq_checks.py`: `schema`, `nulls`, `duplicates`, `freshness` e `consistency` são bloqueantes, e `volume` é alerta. Abaixo está o que daria errado se cada bloqueante fosse rebaixado para alerta.

- **`schema`**: se uma coluna numérica chega como texto (ex.: `quantity = "2un"`), qualquer soma ou média a jusante quebra ou, pior, é coagida em silêncio. Sem a forma certa do dado, nenhum outro check é confiável. Por isso ele é o primeiro da fila.
- **`nulls`**: no dado sujo, `customer_id=22.2%` (2 de 9 linhas). Venda sem cliente não é atribuível: some de relatório por cliente, de comissão e de conciliação. Como alerta, esses 22% seriam publicados como se estivesse tudo bem.
- **`duplicates`**: `Chave ['order_id'] duplicada em 2 linha(s): [{'order_id': 2002}]`. É exatamente o defeito do cenário, o pedido contado duas vezes que inflou o total do mês. Duplicidade de chave infla a métrica principal sem dar erro nenhum, então tem que travar.
- **`consistency`**: `order_id 2005` tem `total_amount = 5000.00`, mas `4 × 890.00 = 3560.00`. O `pipeline.py` recalcula e sobrescreve esse valor em silêncio (`test_pipeline_silently_overwrites_inconsistent_total_amount`). O número publicado sairia "certo" e a origem continuaria errada, sem ninguém saber. O bloqueio é o que força a conversa com o sistema de origem.
- **`freshness`**: `9 linha(s) fora do SLA de 48.0h (pior atraso: 222.0h)`. Promover um dado de 9 dias atrás como se fosse o fechamento de ontem produz um relatório correto na conta e errado no significado.

**Por que `volume` é alerta:** `Volume 9 fora da janela esperada [20, 40]`. Uma carga pequena tem causas legítimas: o job rodou no meio do dia, era feriado, uma região ficou sem vendas. O número de linhas sozinho não diz se o dado está errado; diz só que ele é diferente do habitual. Travar por isso geraria falso positivo recorrente, e o time aprenderia a ignorar o gate. O alerta mantém a visibilidade (aparece em `warning_failures`) sem impedir a promoção. Neste arquivo sujo, de qualquer forma, o gate já reprova pelos quatro bloqueantes.

## 2. Qual seria um SLA de freshness razoável para este pipeline e o que acontece se ele estourar?

Para vendas consumidas pelo **financeiro no fechamento diário**, 48h é razoável. Cobre um dia de atraso da origem mais uma reexecução, sem deixar passar uma carga da semana anterior como se fosse de ontem. No dado sujo, o registro mais recente tem 6 dias e o pior tem 222h, muito além de qualquer SLA diário.

Se o consumidor fosse um **dashboard operacional com SLA de 1h**, a decisão muda:

- atraso passa a ser frequente e muitas vezes transitório (fila, reprocessamento);
- bloquear a cada estouro deixaria o dashboard parado, o que é pior do que mostrar um dado com poucas horas de atraso e um aviso visível;
- nesse caso freshness vira **alerta com paging** (alguém olha agora), e o bloqueio fica reservado a um limite bem maior, por exemplo 24h.

Um detalhe que descobrimos na prática: sem `--reference-datetime`, o check compara contra o relógio real. O `sample_clean.csv` (datas de 13/09/2026) começou a **reprovar sozinho** alguns dias depois de commitado, sem nenhuma mudança de código ou de dado. Por isso o CI e os testes de integração fixam `DQ_REFERENCE_DATETIME=2026-09-13T12:00:00`: mesmo input, mesmo veredito. Em produção, a referência seria o horário de início da execução da carga, registrado no relatório.

## 3. Se o Quality Gate falhar às 3h da manhã, quem é avisado e o que essa pessoa deveria fazer?

Hoje ninguém é avisado. O gate só imprime no log do CI e grava `quality_report.json`, publicado como artifact (`quality-report-clean` / `quality-report-dirty`). Isso serve de evidência, mas não acorda ninguém.

Proposta:

- **Falha bloqueante** vai para o **PagerDuty** do plantão de dados, porque impede a promoção e o financeiro depende dela de manhã. **Falha de alerta** (`volume`) vai para um **canal no Slack**, sem paging.
- Conteúdo da mensagem (tudo já existe no JSON, nada de reler código):
  - arquivo (`input_file`) e `row_count`;
  - `blocking_failures` e o `details` de cada um, ex.: `duplicates: order_id 2002 em 2 linhas`, `consistency: order_id de exemplo [2005]`;
  - link do run do CI e do artifact `quality_report.json`;
  - instante de referência usado no freshness.
- **Primeiro passo do plantonista:** **não promover** (o gate já garante isso) e classificar a falha.
  - Defeito de origem (`duplicates`, `consistency`, `nulls`): abrir chamado para o time do sistema de origem com os `order_id` do relatório, e comunicar ao financeiro que o número do dia está retido.
  - Atraso (`freshness`): verificar se a carga nova chegou e **reprocessar**.
  - **Promover com exceção** só com aprovação do dono do dado e registro escrito (o quê, por quê, quem aprovou). Nunca como atalho padrão.

## 4. O check de training-serving skew (Desafio 6) deveria bloquear o deploy do modelo ou só gerar alerta? Justifiquem.

**Alerta, não bloqueio automático.** O relatório do `make skew-check` mostra:

```text
quantity        3.00 -> 3.00      0.0%  não
unit_price    964.25 -> 1349.95  40.0%  SIM
total_amount 2892.75 -> 4049.85  40.0%  SIM
```

A quantidade não mudou; mudou o preço, uniformemente, em 40%. Isso tem cara de **mudança real de mercado** (reajuste, inflação), não de dado corrompido. O modelo não está "errado". O que acontece é que ele aprendeu um limiar de "alto valor" em outra faixa de preço, e agora vai classificar quase tudo como alto valor.

A diferença para o pipeline de vendas:

- em `check_consistency`, `total_amount != quantity * unit_price` é **erro objetivo**: não existe mundo em que isso esteja certo, então bloquear é seguro;
- no skew, o dado de serving pode estar perfeitamente correto. Bloquear o deploy automaticamente congelaria em produção justamente o modelo antigo, calibrado para um mundo que não existe mais, e impediria a adaptação.

Por isso o job `skew-check` do CI é informativo e não é dependência de `build`. A ação certa diante do alerta é **revisão humana**: confirmar com o negócio se a mudança é real e, se for, retreinar com dados recentes e comparar Champion vs Challenger antes de trocar. O bloqueio só se justificaria se o skew viesse junto de uma falha de qualidade (ex.: preço multiplicado por 100 por erro de unidade), e isso é o gate de dados que deve pegar.

## 5. O que o `quality_report.json` prova — e o que ele NÃO prova?

**Prova:** que os seis checks rodaram sobre aquele arquivo, com aqueles thresholds e aquele instante de referência, e qual foi o resultado de cada um. Como o `SEVERITY` e a referência são fixos, o veredito é reproduzível.

**Não prova:**

- **Regras que nenhum check cobre.** Exemplo concreto do próprio `sample_dirty.csv`: `order_id 2004` tem `quantity = -3` e `total_amount = -750.00`. O `consistency` passa (`-3 × 250 = -750`), e nenhum check de faixa ou domínio existe. Quem barra essa linha hoje é o `validate_orders` do pipeline, não o gate. Um check de domínio (`quantity > 0`, `unit_price >= 0`, `region` em uma lista conhecida) fecharia essa lacuna.
- **Veracidade do dado.** Um pedido inventado, mas bem formado, passa em tudo.
- **Integridade entre cargas.** O check de duplicidade olha só dentro do arquivo; o mesmo `order_id` pode já ter sido carregado ontem.
- **Representatividade do volume.** 30 linhas dentro de `[20, 40]` não garantem que vieram todas as regiões.
- **Nada sobre o arquivo de amanhã.** O relatório vale para aquele input, naquele momento.

## 6. Quais trade-offs vocês assumiram ao definir os thresholds (limite de nulos, janela de volume, tolerância de consistência)?

- **Nulos, 5%** (`limite_percentual_nulos`): tolera um ou outro registro incompleto numa carga de ~30 linhas (1 nulo = 3,3%), mas reprova o dado sujo (22,2%). Com **1%**, uma única linha nula numa carga pequena já travaria tudo; com **10%**, uma em cada dez vendas sem cliente seria aceita. Para `order_id` o limite ideal seria **0%**, porque uma chave nula é sempre defeito. Mantivemos um limite único por simplicidade, mas o trade-off real é ter limites por campo.
- **Volume, `[20, 40]`**: baseado na carga de referência de 30 linhas (±33%). Uma janela mais estreita pegaria desvios menores, mas geraria alerta a cada variação normal de dia da semana. Como `volume` é alerta, preferimos uma janela larga, que só avisa em anomalia grosseira (9 linhas, como no dado sujo). Em produção, a janela deveria vir do histórico (ex.: média ± 3 desvios por dia da semana), não de um número fixo.
- **Consistência, tolerância `0.01`**: é um centavo, o suficiente para absorver arredondamento de ponto flutuante em `quantity * unit_price` sem mascarar erro real (no `order_id 2005` a diferença é de R$ 1.440). Uma tolerância maior aceitaria erros de centavos acumulados em milhares de linhas, e uma zero reprovaria arredondamentos legítimos.
- **Freshness, 48h**: discutido no §2. É a escolha mais dependente do consumidor.

Todo threshold aqui é uma decisão de negócio. O mais importante é que eles estão **explícitos e centralizados** (`run_all_checks` e `SEVERITY`) e aparecem no `details` de cada resultado, então quem lê o relatório sabe contra qual régua o dado foi medido.
