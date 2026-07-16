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

## Deploy na Vercel

A configuracao mais segura para deploy e manter `src/data/generated/results.json`
versionado no Git. Assim, o build remoto nao depende de acessar `../outputs/`
fora da pasta `dashboard/`.

Na interface da Vercel, configure:

```text
Root Directory: dashboard
Install Command: npm install
Build Command: npm run build
Output Directory: dist
```

O arquivo `vercel.json` desta pasta tambem declara esses comandos. Durante o
build, `npm run build` tenta sincronizar `../outputs/results/*.json`; se essa
pasta nao existir no ambiente remoto, o script preserva o JSON agregado ja
versionado em `src/data/generated/results.json`.

## Decisoes tecnicas

- O grafico foi recriado em componente React/CSS a partir de `summary`, sem
  depender dos PNGs em `outputs/reports/`.
- Estados visuais nunca dependem apenas de cor: variantes recomendadas, alertas
  e candidatos tambem recebem texto e icones.
- O dashboard fica em pasta separada e nao interfere no pipeline Python.
