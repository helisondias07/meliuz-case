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

A pergunta central é: qual variante devemos escalar para 100% do tráfego?

A regra usada é:

1. Descartar variantes com `margem_total <= 0`.
   Uma variante que não gera margem positiva não deve ser escalada, mesmo que
   traga volume.
2. Entre as variantes viáveis, olhar a maior `margem_por_comprador`.
   Essa é a métrica principal porque conecta eficiência econômica com usuário
   comprador. Ela é calculada como:

   ```text
   margem_total / compradores_total
   ```

   ou seja, razão agregada do período inteiro, não média das razões diárias.
3. Escolher a baseline entre as variantes viáveis, usando a menor
   `cashback_pct_vendas`.
4. Comparar variantes contra a baseline usando bootstrap por data.
5. Escalar apenas se:
   - o IC95 da diferença de margem por comprador exclui zero;
   - a amostra tem pelo menos 30 dias por grupo.
6. Se a evidência for fraca, recomendar:

   ```text
   Não escalar ainda; manter teste
   ```

O `prob_variante_supera_baseline` aparece no relatório como leitura intuitiva
do bootstrap, mas não é o critério principal de decisão. O critério principal é
o IC95 excluir zero.

## Bootstrap pareado

Nos datasets fornecidos, todas as variantes rodam nas mesmas datas. Por isso, o
bootstrap é pareado por data:

1. Sorteia datas com reposição.
2. Aplica o mesmo conjunto de datas à baseline e à variante.
3. Recalcula, em cada reamostragem:

   ```text
   soma(margem dos dias sorteados) / soma(compradores dos dias sorteados)
   ```

Esse pareamento controla efeitos comuns de calendário, como fim de semana,
promoções e sazonalidade do parceiro.

Se um teste futuro não tiver as mesmas datas em todos os grupos, o código cai
automaticamente para bootstrap independente e marca `pareamento_usado = false`
no relatório. Isso mantém a automação funcionando, mas a estimativa tende a ser
mais conservadora.

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
