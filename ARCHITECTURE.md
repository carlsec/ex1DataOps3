# Architecture Decision

Preencha este documento como parte da entrega. Seja específico: cite checks, thresholds, linhas do `quality_report.json` e trade-offs reais deste laboratório. Evite respostas genéricas.

## 1. Quais checks vocês marcaram como BLOQUEANTES e por quê?

Consulte `SEVERITY` em `src/dq_checks.py`. Para cada check bloqueante, justifique o que aconteceria de errado se ele fosse rebaixado para alerta. Para o único check que veio como alerta (`volume`), justifique por que um volume abaixo do esperado pode ser legítimo e não deveria travar sozinho a esteira.

[Resposta do aluno]

## 2. Qual seria um SLA de freshness razoável para este pipeline e o que acontece se ele estourar?

O laboratório usa 48h como exemplo (`sla_horas` em `check_freshness`). Isso faz sentido para este domínio (vendas)? Depende de quem consome o dado a jusante (financeiro fechando o dia? um dashboard em tempo real?). O que muda na decisão de bloquear vs alertar se o SLA for de 1h em vez de 48h?

[Resposta do aluno]

## 3. Se o Quality Gate falhar às 3h da manhã, quem é avisado e o que essa pessoa deveria fazer?

Hoje o Quality Gate só imprime no terminal do CI e grava `quality_report.json`. Isso é suficiente para acordar alguém? Que canal (Slack, PagerDuty, e-mail) faria sentido, e o que deveria estar na mensagem para que a pessoa de plantão não precise reler o código para entender o que quebrou? Qual é o primeiro passo dela: reprocessar, avisar o time de dados de origem, ou promover mesmo assim com uma exceção documentada?

[Resposta do aluno]

## 4. O check de training-serving skew (Desafio 6) deveria bloquear o deploy do modelo ou só gerar alerta? Justifiquem.

Pensem na diferença entre um pipeline de dados de vendas (o dado errado já aconteceu, é fato passado) e um modelo em produção (o dado de serving pode simplesmente refletir uma mudança real de mercado, não um erro). Bloquear automaticamente o deploy de um modelo por skew pode impedir a adaptação a uma mudança legítima?

[Resposta do aluno]

## 5. O que o `quality_report.json` prova — e o que ele NÃO prova?

Ele prova que os checks rodaram e o resultado que deram para aquele arquivo, naquele momento. O que ele não garante sobre a qualidade dos dados que os checks não cobrem?

[Resposta do aluno]

## 6. Quais trade-offs vocês assumiram ao definir os thresholds (limite de nulos, janela de volume, tolerância de consistência)?

Todo threshold é uma escolha de negócio disfarçada de número. Por que 5% de nulos e não 1% ou 10%? Por que a janela de volume é `[20, 40]` e não mais estreita?

[Resposta do aluno]
