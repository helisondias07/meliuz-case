# Análise de Testes A/B de Cashback - Méliuz

Este projeto foi feito para o case técnico de Estágio em Operações Integradas do
Méliuz.

A pergunta do case é bem direta: dado um teste A/B de cashback, **qual variante
deve ser escalada para 100% do tráfego?**

Minha solução automatiza essa análise para novos CSVs no mesmo formato. Ela gera
um relatório por teste, um JSON estruturado para visualização e uma linha de
acompanhamento em CSV.

## Resultado dos 3 testes

Rodei a análise nos três datasets fornecidos. A recomendação final foi a mesma
nos três casos: **escalar o Grupo 1**.

| Parceiro | Teste | Recomendação | Principal motivo |
|---|---|---|---|
| Parceiro A | 3 grupos, 92 dias | Escalar Grupo 1 | Maior margem por comprador e IC95 robusto |
| Parceiro B | 3 grupos, 61 dias | Escalar Grupo 1 | Melhor combinação de margem e volume |
| Parceiro C | 2 grupos, 45 dias | Escalar Grupo 1 | Grupo 2 zera a margem e é descartado pelo guardrail |

Os relatórios completos ficam em `outputs/reports/`.

Também publiquei um dashboard para visualizar os resultados sem rodar nada
localmente:

**https://meliuz-case.vercel.app/**

## Como pensei a decisão

O caminho mais simples seria olhar para a variante que mais vendeu. Mas, em um
teste de cashback, isso pode levar a uma decisão ruim: uma variante pode vender
mais porque está dando cashback demais, e esse volume extra pode não compensar a
perda de margem.

Por isso, antes de qualquer estatística, usei um guardrail de negócio:

1. Variante com `margem_total <= 0` não pode ser escalada.
2. Entre as variantes viáveis, a métrica principal é `margem_por_comprador`.
3. A comparação estatística só serve para confirmar se a vantagem observada é
   robusta o bastante para virar recomendação.

No Parceiro C, esse guardrail faz diferença: o Grupo 2 tem margem total zero,
porque o cashback consome toda a comissão. Mesmo que ele trouxesse volume, não
faria sentido escalar uma variante que não deixa margem para o Méliuz.

## Métrica principal

A métrica que guia a decisão é:

```text
margem_por_comprador = margem_total / compradores_total
```

Usei a razão agregada do período inteiro, não a média das margens diárias por
comprador. Isso evita dar peso exagerado a dias pequenos ou atípicos.

A baseline é escolhida automaticamente como a variante viável com menor
`cashback_pct_vendas`. Se a variante com menor cashback tiver margem negativa ou
zero, ela não entra como baseline.

## Por que usei bootstrap pareado

Minha primeira versão comparava médias de forma mais direta. Depois, olhando os
dados com calma, vi um detalhe importante: dentro de cada dataset, todas as
variantes rodam nas mesmas datas.

Isso quer dizer que o teste é concorrente. Se um fim de semana, feriado ou
promoção melhora as vendas de um dia, esse efeito aparece em todos os grupos ao
mesmo tempo. Comparar os grupos como se fossem amostras independentes ignora
essa relação.

Por isso usei bootstrap pareado por data:

1. sorteio datas com reposição;
2. aplico o mesmo sorteio à baseline e à variante;
3. recalculo a margem por comprador em cada reamostragem;
4. olho a distribuição das diferenças.

Assim, o efeito comum de calendário tende a cancelar entre os grupos, e a
comparação fica mais focada na diferença entre as variantes.

Se um teste futuro não tiver as mesmas datas em todos os grupos, o código cai
automaticamente para bootstrap independente e marca isso no relatório com
`pareamento_usado: false`.

## Regra final

Uma variante só é recomendada para escala quando:

- tem margem total positiva;
- tem a melhor margem por comprador entre as variantes viáveis;
- o IC95 da diferença contra a baseline não passa por zero;
- o teste tem pelo menos 30 dias por grupo.

Se alguma dessas condições falhar, a recomendação é manter o teste em vez de
forçar uma conclusão.

## Como reproduzir

Instale o projeto:

```bash
python -m pip install -e .[test]
```

Rode os três datasets:

```powershell
python -m meliuz_abtest.cli --input data/dataset_01_parceiroA.csv --test-name "Cashback Parceiro A" --description "Teste de cashback no Parceiro A"
python -m meliuz_abtest.cli --input data/dataset_02_parceiroB.csv --test-name "Cashback Parceiro B" --description "Teste de cashback no Parceiro B"
python -m meliuz_abtest.cli --input data/dataset_03_parceiroC.csv --test-name "Cashback Parceiro C" --description "Teste de cashback no Parceiro C"
```

Cada execução gera:

- relatório e gráfico em `outputs/reports/`;
- JSON estruturado em `outputs/results/`;
- linha consolidada em `outputs/tracking/acompanhamento.csv`.

## Dashboard

O dashboard é uma camada extra de visualização. Ele não recalcula nada; apenas
lê os JSONs gerados pelo pipeline Python.

**Dashboard ao vivo:** https://meliuz-case.vercel.app/

Para rodar localmente:

```bash
cd dashboard
npm install
npm run dev
```

## Google Sheets

O CSV local sempre é gerado. Opcionalmente, o mesmo resultado pode ser enviado
para Google Sheets configurando:

```powershell
$env:GOOGLE_SERVICE_ACCOUNT_JSON = "secrets/google-service-account.json"
$env:SHEET_ID = "id_da_planilha"
$env:SHEET_TAB_NAME = "acompanhamento"
```

Se a integração com Sheets falhar por credencial, rede ou permissão, o pipeline
não quebra. Ele mantém o CSV local como fallback.

## Testes

```bash
python -m pytest -q
```

A suíte cobre limpeza dos dados, cálculo de métricas, bootstrap pareado,
fallback independente, regra de decisão, geração dos relatórios e tracking.

## Limitações

- O dataset não traz usuários expostos, então não dá para calcular conversão
  real. Usei eficiência econômica por comprador como proxy.
- O bootstrap pareado depende de as variantes compartilharem as mesmas datas.
  Quando isso não acontece, o código usa bootstrap independente.
- A baseline é inferida pela menor taxa de cashback entre variantes viáveis. Se
  existir uma marcação explícita de grupo controle no futuro, isso pode virar um
  parâmetro do CLI.
