# Análise de Testes A/B de Cashback - Méliuz

Solução reutilizável em Python para analisar testes A/B de cashback, responder
qual variante deve ser escalada para 100% do tráfego e registrar o resultado em
uma planilha de acompanhamento.

O projeto foi construído para o case técnico de Estágio de Operações Integradas
do Méliuz. A ideia é que uma pessoa do time consiga apontar um novo CSV com o
mesmo schema e receber:

- relatório em Markdown para gestor;
- gráfico comparativo;
- JSON estruturado para consumo por dashboard;
- linha de acompanhamento em CSV e, se configurado, Google Sheets.

## Como instalar

Recomendado usar Python 3.10+.

```bash
python -m pip install -e .[test]
```

Para instalar também as dependências opcionais do Google Sheets:

```bash
python -m pip install -e .[test,sheets]
```

## Como rodar

```bash
python -m meliuz_abtest.cli ^
  --input data/dataset_01_parceiroA.csv ^
  --test-name "Cashback Parceiro A" ^
  --description "Teste de cashback no Parceiro A"
```

No PowerShell, o mesmo comando pode ser escrito em uma linha:

```powershell
python -m meliuz_abtest.cli --input data/dataset_01_parceiroA.csv --test-name "Cashback Parceiro A" --description "Teste de cashback no Parceiro A"
```

Saídas geradas:

- `outputs/reports/<nome_do_teste>.md`
- `outputs/reports/<nome_do_teste>_chart.png`
- `outputs/results/<nome_do_teste>.json`
- `outputs/tracking/acompanhamento.csv`

## Rodando os três datasets

```powershell
python -m meliuz_abtest.cli --input data/dataset_01_parceiroA.csv --test-name "Cashback Parceiro A" --description "Teste de cashback no Parceiro A"
python -m meliuz_abtest.cli --input data/dataset_02_parceiroB.csv --test-name "Cashback Parceiro B" --description "Teste de cashback no Parceiro B"
python -m meliuz_abtest.cli --input data/dataset_03_parceiroC.csv --test-name "Cashback Parceiro C" --description "Teste de cashback no Parceiro C"
```

## Resultado nos datasets fornecidos

| Dataset | Parceiro | Baseline | Decisão | Variante recomendada | Motivo resumido |
|---|---|---|---|---|---|
| `dataset_01_parceiroA.csv` | Parceiro A | Grupo 1 | Escalar | Grupo 1 | Maior margem por comprador viável e IC95 robusto |
| `dataset_02_parceiroB.csv` | Parceiro B | Grupo 1 | Escalar | Grupo 1 | Maior margem por comprador viável e IC95 robusto |
| `dataset_03_parceiroC.csv` | Parceiro C | Grupo 1 | Escalar | Grupo 1 | Grupo 2 tem margem total zero e é descartado pelo guardrail |

Mesmo após trocar a análise inicial simples por bootstrap pareado, guardrails de
negócio e decisão via IC95, a recomendação final continuou Grupo 1 nos três
datasets. Isso aumenta a confiança de que a conclusão não é artefato de um
método estatístico frágil.

## Arquitetura

```text
.
├── data/                         # datasets fornecidos no case
├── outputs/
│   ├── reports/                  # relatórios Markdown e gráficos
│   ├── results/                  # JSONs estruturados para dashboard
│   └── tracking/                 # CSV de acompanhamento
├── secrets/                      # credenciais locais, gitignored
├── src/
│   └── meliuz_abtest/
│       ├── data_loader.py
│       ├── metrics.py
│       ├── statistics.py
│       ├── decision.py
│       ├── report.py
│       ├── tracking.py
│       └── cli.py
└── tests/
```

Responsabilidades:

- `data_loader.py`: lê o CSV, valida schema, normaliza moedas, remove duplicatas
  e linhas inválidas, e registra contadores de qualidade de dados.
- `metrics.py`: calcula métricas por variante, como GMV, comissão, cashback,
  margem total, margem por comprador, ticket médio e ROI de cashback.
- `statistics.py`: escolhe a baseline viável e estima incerteza via bootstrap.
- `decision.py`: aplica a regra final de escala ou manter teste.
- `report.py`: gera Markdown, gráfico e JSON estruturado.
- `tracking.py`: registra a linha consolidada em CSV e, opcionalmente, Google Sheets.
- `cli.py`: ponto de entrada único do pipeline.

## Lógica de decisão

A pergunta que esse case faz é simples de enunciar e chata de responder direito:
qual variante de cashback devemos escalar pra 100% do tráfego?

O jeito mais rápido de responder seria "a que vendeu mais". Mas isso é uma
armadilha clássica: uma variante pode vender mais só porque está queimando
cashback demais, o que destrói a margem do Méliuz mesmo trazendo volume. Então
a primeira regra, antes de qualquer estatística, é um guardrail de negócio:

1. **Descarta qualquer variante com `margem_total <= 0`.** Ponto final, não
   importa o volume. O dataset do Parceiro C tem exatamente esse caso: o Grupo 2
   zera a margem porque o cashback comeu toda a comissão. Esse alerta aparece
   antes mesmo de rodar qualquer teste estatístico.
2. **Entre as que sobraram, a métrica que decide é `margem_por_comprador`**,
   não margem total nem GMV. Ela é calculada como `margem_total /
   compradores_total`: uma razão do período inteiro, não a média das razões
   diárias. Isso importa porque um dia com poucos compradores e margem estranha
   não deveria pesar igual a um dia normal na média.
3. A baseline, contra quem comparar as outras, é a variante com menor
   `cashback_pct_vendas`, mas só entre as variantes viáveis. Isso pareceu óbvio
   até eu perceber um edge case: e se a variante de menor cashback% for
   justamente uma com margem negativa? Nesse caso a baseline vira a segunda
   menor, não a inviável.
4. Daí entra o bootstrap, explicado na seção seguinte, para verificar se a
   vantagem da líder é real ou se é só ruído.
5. Só escala se **duas coisas** forem verdade ao mesmo tempo: o IC95 da
   diferença de margem por comprador não passa por zero, e o teste rodou pelo
   menos 30 dias por grupo. Se qualquer uma falhar, a resposta é "não escalar
   ainda; manter teste", mesmo que a variante pareça melhor na média observada.
   Forçar uma decisão em cima de dado insuficiente é pior do que admitir que
   ainda não dá pra saber.

Uma coisa que me deixou mais confiante nessa lógica: rodei os 3 datasets
primeiro com uma versão bem mais simples, baseada em comparação direta de
médias, e depois com bootstrap pareado + guardrails. A resposta final não mudou:
Grupo 1 nos três casos. Isso não prova que a conclusão está certa, mas mostra
que ela não é um artefato de ter escolhido um método estatístico frágil.

## Por que bootstrap pareado, e não um teste-t comum

Minha primeira versão usava Welch's t-test, que é o approach mais direto que
qualquer curso de estatística ensina para comparar duas médias. Funcionava, mas
tinha um problema que só percebi depois de olhar os dados com mais calma:
**todas as variantes de um mesmo dataset rodam exatamente nas mesmas datas.**
Não é um teste sequencial, primeiro Grupo 1 em um mês e depois Grupo 2 no mês
seguinte. É concorrente: todo mundo ao mesmo tempo.

Isso muda a estatística certa a usar. Se um fim de semana ou uma promoção do
parceiro faz todo mundo vender mais naquele dia, esse efeito bate em todas as
variantes ao mesmo tempo. Comparar os grupos como se fossem amostras
independentes, que é o que o t-test simples faz, ignora essa correlação e infla
a incerteza sem necessidade.

A correção é o bootstrap **pareado por data**:

1. Sorteia um conjunto de datas com reposição, como no bootstrap comum.
2. Aplica **o mesmo sorteio de datas** para a baseline e para a variante, já que
   ambas têm exatamente as mesmas datas disponíveis.
3. Recalcula, para cada reamostragem, a soma da margem dos dias sorteados
   dividida pela soma de compradores dos mesmos dias sorteados, para cada grupo.
4. Repete isso milhares de vezes e olha a distribuição das diferenças.

Pareando dessa forma, o efeito "todo mundo vendeu mais nesse dia" cancela entre
os dois grupos, e sobra só a diferença que realmente vem da variante em si.
Isso deixa a estimativa mais precisa, com IC95 mais estreito, do que o bootstrap
independente teria dado no mesmo cenário. Testei isso na prática; não é só
teoria.

Se um teste futuro não tiver as mesmas datas em todos os grupos, por exemplo se
alguém rodar as variantes em janelas diferentes, o código cai automaticamente
para bootstrap independente e marca isso no relatório (`pareamento_usado:
false`), para deixar claro que a estimativa naquele caso é mais conservadora.

## Google Sheets

O CSV de acompanhamento é sempre gravado em:

```text
outputs/tracking/acompanhamento.csv
```

Para também escrever no Google Sheets:

1. Crie uma Service Account no Google Cloud.
2. Ative a Google Sheets API.
3. Baixe o JSON da Service Account.
4. Salve o arquivo em `secrets/`, por exemplo:

   ```text
   secrets/google-service-account.json
   ```

5. Compartilhe a planilha com o e-mail da Service Account.
6. Configure as variáveis de ambiente.

No PowerShell:

```powershell
$env:GOOGLE_SERVICE_ACCOUNT_JSON = "secrets/google-service-account.json"
$env:SHEET_ID = "id_da_planilha"
$env:SHEET_TAB_NAME = "acompanhamento"
```

`SHEET_TAB_NAME` é opcional. Se não for informado, o padrão é `acompanhamento`.

Se a escrita no Sheets falhar por credencial, rede ou permissão, o pipeline não
quebra. Ele mostra um aviso e mantém o CSV local como fallback.

## Dashboard web

Ha um dashboard React em `dashboard/` para visualizar os JSONs gerados em
`outputs/results/`. Ele e um adicional de portfolio, nao o entregavel core do
case nem uma nova etapa de calculo.

Para rodar:

```bash
cd dashboard
npm install
npm run dev
```

O dashboard sincroniza os resultados antes do `dev` e do `build`; veja
`dashboard/README.md` para detalhes.

### Dashboard ao vivo

**A forma mais rapida de ver os resultados e acessar o dashboard publicado:**

https://meliuz-case.vercel.app/

Esse link permite revisar os testes sem clonar o repositorio e sem rodar nada
localmente. A versao local em `dashboard/README.md` continua documentada para
quem quiser executar, editar ou validar o app na propria maquina.

Como usar:

- Na tela de lista, cada card representa um teste A/B analisado. A pill colorida
  no canto mostra a decisao final: verde para `Escalar [variante]` ou o estado
  visual equivalente quando a recomendacao for manter o teste. O indicador logo
  abaixo mostra se existe alerta critico de margem.
- Clique em um card para abrir o detalhe do teste.
- No detalhe, o resumo executivo mostra a decisao e o motivo em texto. Ao lado,
  aparecem a confianca estatistica, a baseline usada e quantas alternativas
  foram comparadas.
- Alertas em vermelho e ressalvas em ambar aparecem quando existirem. Alertas
  sao problemas criticos que descartam uma variante, como margem negativa.
  Ressalvas sao avisos que nao descartam a variante, mas pedem cautela, como
  amostra pequena.
- O grafico de margem por comprador compara as variantes com barras coloridas
  por status: verde para a recomendada, ambar para candidata nao confirmada e
  vermelho para alerta.
- A tabela de resumo por variante lista todas as metricas de negocio calculadas.
- A tabela de comparacao estatistica mostra se o bootstrap foi pareado ou
  independente, o intervalo de confianca de 95% e se a amostra foi considerada
  suficiente, com pelo menos 30 dias.

O dashboard e 100% somente leitura. Ele nao recalcula metricas nem altera dados;
apenas exibe os resultados ja processados pelo pipeline Python em
`outputs/results/*.json`. E uma camada adicional de visualizacao da Fase 2, nao
o entregavel core do case.

## Testes

```bash
python -m pytest -q
```

A suíte cobre:

- schema ausente e dados ruins no CSV;
- formatos mistos de moeda;
- duplicatas;
- variantes inválidas após limpeza;
- métricas de negócio;
- bootstrap pareado e fallback independente;
- regra de decisão;
- relatório Markdown/JSON/gráfico;
- tracking em CSV e mocks de Google Sheets.

## Limitações conhecidas

- O dataset não informa usuários expostos por variante, então não é possível
  calcular conversão real. A decisão usa eficiência econômica entre compradores.
- O bootstrap pareado assume que as variantes compartilham as mesmas datas. Se
  não compartilharem, há fallback independente.
- A baseline é escolhida automaticamente entre variantes viáveis pela menor taxa
  de cashback sobre GMV. Se o time tiver uma marcação explícita de controle no
  futuro, isso pode virar parâmetro do CLI.
- A recomendação é conservadora: se a evidência estatística não for robusta, o
  resultado pode ser "manter teste" mesmo quando uma variante parece melhor na
  média observada.
