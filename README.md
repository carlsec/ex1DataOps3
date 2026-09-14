# Ex3 — Verde não significa correto

Laboratório da disciplina **Cultura e Práticas de DataOps e MLOps**.

Este repositório é a evolução natural de [ex1DataOps](https://github.com/faberhenrique/ex1DataOps) e [ex2DataOps](https://github.com/faberhenrique/ex2DataOps). O Ex1 construiu uma esteira simples de CI/CD. O Ex2 tornou o sistema reproduzível: container, IaC, rollback por artefato versionado. Os dois resolvem a pergunta "isso executa de forma confiável?". Este Ex3 pergunta outra coisa, que fica exposta só depois que as duas primeiras já foram respondidas:

> Verde não significa correto. Significa apenas que nada quebrou tecnicamente.

## Contexto

Depois do Ex2, você tem um pipeline que roda em qualquer máquina, empacotado, versionado, com rollback por artefato. Isso é necessário — e não é suficiente. Um pipeline pode:

- executar sem lançar nenhuma exceção;
- gravar um CSV de saída no lugar certo;
- fazer o CI passar do início ao fim;
- e ainda assim publicar um número errado.

CI verde prova que o **código** rodou. Não prova que o **dado** está correto. São duas perguntas diferentes, e a segunda não aparece sozinha: alguém precisa decidir explicitamente o que checar, o que é grave o suficiente para travar uma promoção, e o que é só motivo de alerta.

## Cenário

O pipeline de vendas do Ex1/Ex2 recebe um novo arquivo de um sistema de origem. O CI roda, os testes unitários passam, o build é gerado, o deploy acontece sem erro. Duas semanas depois, o time financeiro percebe que o total de vendas do mês está inflado. Ninguém recebeu alerta. Não houve exceção, não houve rollback, não houve nenhum sinal vermelho em lugar nenhum — porque nenhum código jamais verificou se **aquele dado específico** fazia sentido.

Investigando, aparecem: um `order_id` duplicado contado duas vezes, um `total_amount` que não batia com `quantity * unit_price` (e que o pipeline recalculou e sobrescreveu em silêncio), e uma carga que chegou com metade das linhas do normal sem que ninguém notasse.

A missão deste laboratório é impedir que esse cenário se repita — não com mais código de transformação, mas com um **Quality Gate**: uma etapa da esteira que roda checks de qualidade de dados e decide, com evidência registrada, se o resultado pode ser promovido.

## Missão

Você deve ser capaz de:

1. rodar o pipeline contra um dado propositalmente ruim e identificar o que quebra — e o que **não** quebra, silenciosamente;
2. implementar checks de qualidade de dados isolados e testáveis;
3. construir um Quality Gate que decide, com base nesses checks, se algo pode avançar;
4. colocar esse gate na esteira de CI, como uma etapa que efetivamente barra o pipeline;
5. justificar por escrito, em `ARCHITECTURE.md`, o que é bloqueante e o que é apenas alerta;
6. (opcional) detectar um desvio entre a distribuição de dados de treino e de produção antes que ele vire um modelo tomando decisões erradas silenciosamente.

## Pré-requisitos

- Python 3.11+ (3.12 recomendado)
- Make (opcional, apenas atalhos)

## Como começar

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
make install                       # ou: pip install -r requirements-dev.txt
```

```bash
make test
```

Depois, rode o pipeline contra o dado limpo e contra o dado sujo, e compare o que acontece:

```bash
python -m src.pipeline
python -m src.quality_gate --input data/input/sample_clean.csv
python -m src.quality_gate --input data/input/sample_dirty.csv
```

## Desafios

### Desafio 1 — Rode o pipeline com o dado sujo e veja o que quebra (ou pior, o que NÃO quebra silenciosamente)

Rode `src/pipeline.py` contra `data/input/sample_dirty.csv`. Algumas coisas vão estourar exceção imediatamente — o pipeline já validava nulos e `quantity` negativa desde o Ex1/Ex2. Mas nem tudo quebra.

Pergunte-se: se você removesse só as linhas com nulo e `quantity` negativa, o resto do arquivo passaria pelo pipeline sem nenhum erro. E, no entanto, ainda restariam nesse arquivo: um `order_id` duplicado, uma linha com `total_amount` que não bate com `quantity * unit_price` (que o pipeline recalcula e sobrescreve, mascarando o problema de origem — veja `test_pipeline_silently_overwrites_inconsistent_total_amount` em `tests/test_pipeline.py`), e uma carga com bem menos linhas do que o normal.

Perguntas:

- Qual defeito gera uma exceção e qual passa batido?
- Um pipeline que "sobrescreve e conserta" um dado de origem errado está ajudando ou escondendo o problema?
- Validação de esquema/tipo (o que o Ex2 já fazia) é a mesma coisa que qualidade de dados?

### Desafio 2 — Implemente os checks de qualidade de dados

Em `src/dq_checks.py`, cada check é uma função pura: recebe um `DataFrame` (e parâmetros), devolve `{"check", "passed", "details"}`. Nenhuma delas decide sozinha se deve travar a esteira — isso é responsabilidade de `SEVERITY`, um dicionário separado da lógica de cada check, propositalmente fácil de editar.

Implemente (ou revise) e teste:

- `check_schema` — colunas esperadas presentes, com tipo compatível;
- `check_nulls` — percentual de nulos em campos obrigatórios, contra um limite;
- `check_duplicates` — duplicidade por chave (`order_id`);
- `check_volume` — número de linhas dentro de uma janela esperada;
- `check_freshness` — idade de `event_date` contra um SLA em horas;
- `check_consistency` — `total_amount == quantity * unit_price`, com tolerância de arredondamento.

Perguntas:

- Por que cada check devolve um `dict` com `details` em vez de só `True`/`False`?
- O que aconteceria se `check_freshness` comparasse contra uma data fixa no código, em vez de aceitar um `reference_time`?

### Desafio 3 — Construa o Quality Gate e decida o que é bloqueante

`src/quality_gate.py` roda todos os checks contra um arquivo, imprime um relatório legível, grava `quality_report.json` e retorna o exit code que trava (ou libera) o CI:

```bash
python -m src.quality_gate --input data/input/sample_clean.csv
echo "exit code: $?"     # 0

python -m src.quality_gate --input data/input/sample_dirty.csv
echo "exit code: $?"     # 1
```

A decisão de bloquear vem só dos checks marcados `BLOQUEANTE` em `SEVERITY` (`src/dq_checks.py`). Um check `ALERTA` que falha aparece no relatório e no JSON, mas nunca muda o exit code.

Perguntas:

- Por que `volume` está marcado como alerta e não bloqueio neste laboratório? Vocês concordam?
- O que faz sentido logar em `details` para que quem for investigar às 3h da manhã não precise ler o código-fonte do check?

### Desafio 4 — Coloque o Quality Gate na esteira de CI

O workflow em `.github/workflows/ci.yml` já materializa a sequência:

```text
lint → unit-tests → quality-gate → build
```

Cada job só roda se o anterior passou (`needs:`). O job `quality-gate` roda o gate contra `sample_clean.csv`; se ele falhar, `build` nunca executa.

Há também um job `quality-gate-demo-dirty`, separado e com `continue-on-error: true`, que roda o gate contra `sample_dirty.csv` **só para demonstrar** que ele reprova (exit code 1) sem derrubar o workflow principal.

Perguntas:

- Por que a demonstração do dado sujo precisa estar isolada da esteira principal, em vez de ser mais um step do job `quality-gate`?
- O que muda no significado de "CI verde" antes e depois deste job existir?

### Desafio 5 — Reflita em ARCHITECTURE.md sobre os critérios de bloqueio

Preencha `ARCHITECTURE.md` respondendo, com exemplos concretos deste repositório (nomes de check, valores de threshold, trechos de `quality_report.json`):

- quais checks vocês marcaram como bloqueantes e por quê;
- qual seria um SLA de freshness razoável para este pipeline;
- quem é avisado se o gate falhar de madrugada, e o que essa pessoa deveria fazer;
- se o check de skew (Desafio 6) deveria bloquear o deploy do modelo ou só alertar.

### Desafio 6 (opcional) — Detecte training-serving skew entre treino e "produção"

`src/ml_skew_check.py` treina uma regressão logística simples para prever se uma venda é "de alto valor" (`total_amount` acima da mediana), usando `sample_clean.csv` como treino. `sample_serving.csv` simula uma mudança real de mercado: mesma estrutura, `unit_price` em média 40% maior.

```bash
make skew-check
```

`compare_train_serving` compara média e desvio padrão de cada feature numérica entre os dois conjuntos e sinaliza quando a variação passa de 20% — a checagem clássica de *training-serving skew*.

Perguntas:

- O relatório aponta `unit_price` e `total_amount` como "estourados". Isso significa que o modelo está errado, ou que o mundo mudou?
- Esse tipo de checagem deveria travar automaticamente um deploy de modelo, do mesmo jeito que `check_consistency` trava a promoção de um CSV?

## Critérios de aceite

- [ ] `pytest` passa (unitários de pipeline, unitários de cada DQ check, integração do quality gate).
- [ ] `python -m src.quality_gate --input data/input/sample_clean.csv` retorna exit code 0.
- [ ] `python -m src.quality_gate --input data/input/sample_dirty.csv` retorna exit code 1.
- [ ] `quality_report.json` é gerado com o resultado estruturado de cada check.
- [ ] `SEVERITY` (em `src/dq_checks.py`) deixa explícito e fácil de alterar o que é bloqueante e o que é alerta.
- [ ] O CI executa `lint → unit-tests → quality-gate → build` em sequência, e o `quality-gate` efetivamente barra o `build` se falhar.
- [ ] Existe uma demonstração do Quality Gate reprovando o dado sujo, sem quebrar o workflow principal.
- [ ] `ARCHITECTURE.md` está preenchido com justificativas específicas deste repositório.
- [ ] (Opcional) `src/ml_skew_check.py` roda e reporta o skew entre `sample_clean.csv` e `sample_serving.csv`.

## Entregáveis

- código do pipeline, dos checks de qualidade de dados e do Quality Gate;
- `data/input/sample_clean.csv` e `data/input/sample_dirty.csv` (e, se aplicável, `sample_serving.csv`);
- testes unitários e de integração (`tests/`);
- `.github/workflows/ci.yml` com o gate na esteira;
- `quality_report.json` de exemplo (gerado por vocês, não precisa ser commitado);
- `ARCHITECTURE.md` preenchido.

## Avaliação

Nota total: **10 pontos**.

| Critério | Pontos |
|----------|--------|
| DQ checks corretos (schema, nulls, duplicates, volume, freshness, consistency) | 3,0 |
| Quality Gate funcional (relatório, JSON, exit code correto) | 2,5 |
| CI com gate bloqueando de fato o build | 2,0 |
| Testes unitários e de integração | 1,5 |
| `ARCHITECTURE.md` e justificativa de bloqueante vs alerta | 1,0 |

## Relação com o Ex2

| Ex2 | Ex3 |
|-----|-----|
| Pergunta: "isso executa em qualquer máquina?" | Pergunta: "o resultado está correto?" |
| CI valida código e constrói imagem | CI também valida **dado**, com um gate dedicado |
| Rollback por artefato versionado | "Rollback" de promoção: dado ruim nunca chega a ser promovido |
| Reprodutibilidade de ambiente | Reprodutibilidade de **decisão** sobre qualidade (mesmo input, mesmo veredito) |
| Sucesso = container sobe e roda | Sucesso = container roda **e** os dados que ele produziu passam no gate |
| Sem noção de "dado válido" vs "dado inválido" | Checks explícitos, com severidade configurável (`SEVERITY`) |

## Princípio

> Verde não significa correto. Significa apenas que nada quebrou tecnicamente.
