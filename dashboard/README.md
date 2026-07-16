# Dashboard web

Dashboard estatico em Vite + React para visualizar os JSONs gerados pelo pipeline
do case. Ele nao recalcula metricas; apenas sincroniza os arquivos de
`../outputs/results/*.json` para um JSON agregado usado pelo app.

## Como rodar

Na raiz do projeto, gere primeiro os resultados. Depois:

```bash
cd dashboard
npm install
npm run dev
```

O comando `npm run dev` executa automaticamente:

```bash
npm run sync:data
```

Esse script le `../outputs/results/*.json` e gera
`src/data/generated/results.json`. O mesmo passo roda antes de `npm run build`.

## Decisoes tecnicas

- O grafico foi recriado em componente React/CSS a partir de `summary`, sem
  depender dos PNGs em `outputs/reports/`.
- Estados visuais nunca dependem apenas de cor: variantes recomendadas, alertas
  e candidatos tambem recebem texto e icones.
- O dashboard fica em pasta separada e nao interfere no pipeline Python.
