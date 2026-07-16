# Skill: Analisar Teste A/B de Cashback - Méliuz

Use esta skill quando o usuário pedir para analisar um CSV de teste A/B de
cashback e responder qual variante deve ser escalada para 100% do tráfego.

Exemplos de pedido:

- "Analisa esse teste de cashback, o arquivo está em `data/teste.csv`."
- "Qual grupo devemos escalar nesse A/B?"
- "Roda o dataset do Parceiro B e atualiza a planilha de acompanhamento."

## Pré-requisitos

O CSV deve ter este schema:

| Coluna | Descrição |
|---|---|
| `Data` | Data da observação, em `YYYY-MM-DD` |
| `Grupos de usuários` | Variante do teste, como `Grupo 1`, `Grupo 2` |
| `Parceiro` | Nome do parceiro |
| `compradores` | Usuários únicos que compraram no dia |
| `comissão` | Comissão paga pelo parceiro ao Méliuz |
| `cashback` | Cashback distribuído aos usuários |
| `vendas totais` | GMV do dia |

O número de linhas, variantes, parceiro e período pode variar. O código não
deve ser alterado entre datasets; apenas o `--input` muda.

## Instalação

Se o pacote ainda não estiver instalado:

```bash
python -m pip install -e .[test]
```

Se for usar Google Sheets:

```bash
python -m pip install -e .[test,sheets]
```

## Como rodar a análise

Comando padrão:

```bash
python -m meliuz_abtest.cli --input <caminho_csv> --test-name "<nome_do_teste>" --description "<descrição>"
```

Exemplo:

```bash
python -m meliuz_abtest.cli --input data/dataset_01_parceiroA.csv --test-name "Cashback Parceiro A" --description "Teste de cashback no Parceiro A"
```

O CLI gera:

- relatório Markdown em `outputs/reports/`;
- gráfico PNG em `outputs/reports/`;
- JSON estruturado em `outputs/results/`;
- registro consolidado em `outputs/tracking/acompanhamento.csv`;
- registro no Google Sheets, se as variáveis de ambiente estiverem configuradas.

## Google Sheets

O CSV local é sempre escrito. Sheets é opcional.

Variáveis esperadas:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `SHEET_ID`
- `SHEET_TAB_NAME` opcional, padrão `acompanhamento`

No PowerShell:

```powershell
$env:GOOGLE_SERVICE_ACCOUNT_JSON = "secrets/google-service-account.json"
$env:SHEET_ID = "id_da_planilha"
$env:SHEET_TAB_NAME = "acompanhamento"
```

Se o Sheets falhar, não interrompa o fluxo. O CSV local é o fallback esperado.

## Como interpretar a saída

O terminal mostra:

- caminho do relatório;
- caminho do JSON;
- caminho do CSV de acompanhamento;
- status do Google Sheets;
- baseline usada;
- ação final;
- variante recomendada, se houver;
- motivo;
- alertas e ressalvas.

Valores possíveis para `acao`:

- `escalar`: a variante pode ir para 100% do tráfego;
- `manter_teste`: não há evidência suficiente ou nenhuma variante é viável.

## Regra de decisão

1. Descartar variantes com `margem_total <= 0`.
2. Entre variantes viáveis, priorizar maior `margem_por_comprador`.
3. Escolher baseline viável com menor `cashback_pct_vendas`.
4. Comparar variantes contra baseline por bootstrap.
5. Usar bootstrap pareado por data quando os grupos têm as mesmas datas.
6. Se as datas não coincidirem, usar fallback independente e avisar no relatório.
7. Escalar somente se:
   - IC95 da diferença de margem por comprador exclui zero;
   - há pelo menos 30 dias por grupo.

`prob_variante_supera_baseline` é leitura complementar, não critério principal.

## Ao responder para o usuário

Depois de rodar o comando, responda de forma objetiva:

```text
Análise concluída.
Relatório: outputs/reports/...
JSON: outputs/results/...
Tracking: outputs/tracking/acompanhamento.csv
Google Sheets: atualizado / não configurado
Decisão: escalar Grupo X / manter teste
Motivo: ...
Alertas/Ressalvas: ...
```

Não prometa que Sheets foi atualizado se o terminal disser `não configurado /
pulado` ou se houver aviso de falha.

## Datasets de exemplo

```bash
python -m meliuz_abtest.cli --input data/dataset_01_parceiroA.csv --test-name "Cashback Parceiro A" --description "Teste de cashback no Parceiro A"
python -m meliuz_abtest.cli --input data/dataset_02_parceiroB.csv --test-name "Cashback Parceiro B" --description "Teste de cashback no Parceiro B"
python -m meliuz_abtest.cli --input data/dataset_03_parceiroC.csv --test-name "Cashback Parceiro C" --description "Teste de cashback no Parceiro C"
```

Resultado validado nos datasets fornecidos:

- Parceiro A: escalar `Grupo 1`;
- Parceiro B: escalar `Grupo 1`;
- Parceiro C: escalar `Grupo 1`, com alerta de margem zero no `Grupo 2`.

## Testes

Para validar o projeto:

```bash
python -m pytest -q
```
