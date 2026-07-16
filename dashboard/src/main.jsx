import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  ShieldCheck,
  TrendUp,
  Warning,
  XCircle
} from "@phosphor-icons/react";
import "@fontsource/space-grotesk/latin-ext-500.css";
import "@fontsource/space-grotesk/latin-ext-700.css";
import "@fontsource/source-sans-3/latin-ext-400.css";
import "@fontsource/source-sans-3/latin-ext-600.css";
import "@fontsource/source-sans-3/latin-ext-700.css";
import "@fontsource/ibm-plex-mono/latin-ext-500.css";
import results from "./data/generated/results.json";
import meliuzLogo from "./assets/meliuz.png";
import "./styles.css";

const moneyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2
});

const compactMoneyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1
});

const numberFormatter = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 0
});

const decimalFormatter = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 2
});

const percentFormatter = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 1
});

function formatDate(value) {
  if (!value) return "Data indisponivel";
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

function getRecommendedSummary(test) {
  return test.summary?.find(
    (item) => item.variante === test.decision?.variante_recomendada
  );
}

function hasNegativeMargin(test) {
  return test.summary?.some((item) => Number(item.margem_total) <= 0);
}

function getDecisionTone(test) {
  if (test.decision?.acao === "escalar") return "confirmed";
  return "candidate";
}

function getVariantTone(test, row) {
  if (Number(row.margem_total) <= 0) return "danger";
  if (row.variante === test.decision?.variante_recomendada) return "confirmed";
  return "candidate";
}

function toneLabel(tone) {
  if (tone === "danger") return "Alerta";
  if (tone === "confirmed") return "Recomendada";
  return "Candidata";
}

function StatusIcon({ tone, size = 18 }) {
  if (tone === "danger") return <XCircle size={size} weight="duotone" />;
  if (tone === "confirmed") return <CheckCircle size={size} weight="duotone" />;
  return <Warning size={size} weight="duotone" />;
}

function App() {
  const [selectedId, setSelectedId] = useState(null);
  const selectedTest = useMemo(
    () => results.find((item) => item.id === selectedId),
    [selectedId]
  );

  return (
    <main className="app-shell">
      {selectedTest ? (
        <DetailScreen test={selectedTest} onBack={() => setSelectedId(null)} />
      ) : (
        <ListScreen tests={results} onSelect={setSelectedId} />
      )}
    </main>
  );
}

function ListScreen({ tests, onSelect }) {
  return (
    <section className="screen fade-in">
      <BrandHeader />

      <header className="page-header">
        <div>
          <p className="kicker">Dashboard executivo</p>
          <h1>Resultados dos testes A/B de cashback</h1>
          <p className="lead">
            Resultados consolidados para leitura gerencial dos testes de cashback.
          </p>
        </div>
        <div className="count-block" aria-label="Total de testes analisados">
          <span>{tests.length}</span>
          <small>testes analisados</small>
        </div>
      </header>

      {tests.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="test-list">
          {tests.map((test, index) => (
            <TestCard
              key={test.id}
              test={test}
              index={index}
              onSelect={() => onSelect(test.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <Warning size={28} weight="duotone" />
      <h2>Nenhum resultado sincronizado</h2>
      <p>
        Gere arquivos em <code>outputs/results/*.json</code> e
        depois execute <code>npm run dev</code> dentro de <code>dashboard/</code>.
      </p>
    </div>
  );
}

function TestCard({ test, index, onSelect }) {
  const recommended = getRecommendedSummary(test);
  const alert = hasNegativeMargin(test);
  const tone = getDecisionTone(test);
  const actionLabel =
    test.decision?.acao === "escalar" ? "Escalar" : "Manter teste";

  return (
    <button
      className="test-card"
      style={{ "--delay": `${index * 70}ms` }}
      onClick={onSelect}
      type="button"
    >
      <div className="card-main">
        <div className="card-title-block">
          <span className="partner">{test.meta?.parceiro ?? "Parceiro nao informado"}</span>
          <h2>{test.test_name}</h2>
          <p>
            {formatDate(test.meta?.periodo_inicio)} a {formatDate(test.meta?.periodo_fim)}
          </p>
        </div>

        <div className="card-metrics" aria-label="Resumo do teste">
          <Metric label="Variante" value={test.decision?.variante_recomendada ?? "-"} />
          <Metric
            label="Margem por comprador"
            value={
              recommended
                ? moneyFormatter.format(recommended.margem_por_comprador)
                : "-"
            }
          />
          <Metric
            label="Comparacoes"
            value={test.decision?.evidencia_estatistica?.alternativas_comparadas ?? 0}
          />
        </div>
      </div>

      <div className="card-decision">
        <span className={`decision-pill ${tone}`}>
          <StatusIcon tone={tone} />
          {actionLabel} {test.decision?.variante_recomendada ?? ""}
        </span>
        <span className={`alert-chip ${alert ? "danger" : "quiet"}`}>
          {alert ? <XCircle size={17} weight="duotone" /> : <ShieldCheck size={17} weight="duotone" />}
          {alert ? "Alerta de margem" : "Sem alerta critico"}
        </span>
        <ArrowRight className="arrow" size={21} />
      </div>
    </button>
  );
}

function Metric({ label, value }) {
  return (
    <span className="metric">
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  );
}

function DetailScreen({ test, onBack }) {
  const recommended = getRecommendedSummary(test);
  const alerts = test.decision?.alertas ?? [];
  const caveats = test.decision?.ressalvas ?? [];

  return (
    <section className="screen detail-screen fade-in">
      <BrandHeader />

      <button className="back-button" type="button" onClick={onBack}>
        <ArrowLeft size={18} />
        Voltar aos testes
      </button>

      <header className="detail-header">
        <div>
          <p className="kicker">{test.meta?.parceiro ?? "Parceiro"} · {test.description}</p>
          <h1>{test.test_name}</h1>
          <p className="lead">
            {formatDate(test.meta?.periodo_inicio)} a {formatDate(test.meta?.periodo_fim)}
          </p>
        </div>
        <span className={`decision-pill large ${getDecisionTone(test)}`}>
          <TrendUp size={22} weight="duotone" />
          {test.decision?.acao === "escalar" ? "Escalar" : "Manter teste"}{" "}
          {test.decision?.variante_recomendada ?? ""}
        </span>
      </header>

      <section className="executive-panel">
        <div className="memo">
          <span className="memo-label">Resumo executivo</span>
          <h2>{test.decision?.motivo}</h2>
          <div className="memo-facts">
            <Fact
              label="Confianca estatistica"
              value={test.decision?.confiavel_estatisticamente ? "Confiavel" : "Inconclusiva"}
            />
            <Fact
              label="Baseline"
              value={test.decision?.evidencia_estatistica?.baseline ?? "-"}
            />
            <Fact
              label="Alternativas"
              value={test.decision?.evidencia_estatistica?.alternativas_comparadas ?? 0}
            />
          </div>
        </div>
        <NoticeList title="Alertas" tone="danger" items={alerts} empty="Sem alerta critico." />
        <NoticeList title="Ressalvas" tone="candidate" items={caveats} empty="Sem ressalvas." />
      </section>

      <section className="two-column">
        <div className="section-block">
          <div className="section-heading">
            <h2>Margem por comprador</h2>
            <p>Grafico SVG recriado a partir de <code>summary</code>.</p>
          </div>
          <MarginChart test={test} />
        </div>

        <div className="section-block compact">
          <div className="section-heading">
            <h2>Decisao em numeros</h2>
            <p>A variante recomendada aparece com texto e icone, alem da cor.</p>
          </div>
          <div className="numeric-stack">
            <Fact
              label="Variante recomendada"
              value={test.decision?.variante_recomendada ?? "-"}
            />
            <Fact
              label="Margem por comprador"
              value={recommended ? moneyFormatter.format(recommended.margem_por_comprador) : "-"}
            />
            <Fact
              label="Margem total"
              value={recommended ? compactMoneyFormatter.format(recommended.margem_total) : "-"}
            />
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <h2>Resumo por variante</h2>
          <p>Metricas consolidadas por variante.</p>
        </div>
        <SummaryTable test={test} />
      </section>

      <section className="section-block">
        <div className="section-heading">
          <h2>Comparacao estatistica</h2>
          <p>Bootstrap pareado ou independente conforme marcado no JSON.</p>
        </div>
        <ComparisonTable rows={test.comparison ?? []} />
      </section>
    </section>
  );
}

function BrandHeader() {
  return (
    <div className="brand-header">
      <img className="meliuz-logo" src={meliuzLogo} alt="Meliuz" />
    </div>
  );
}

function Fact({ label, value }) {
  return (
    <div className="fact">
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}

function NoticeList({ title, tone, items, empty }) {
  const hasItems = items.length > 0;
  return (
    <div className={`notice ${tone} ${hasItems ? "" : "muted"}`}>
      <div className="notice-title">
        <StatusIcon tone={hasItems ? tone : "confirmed"} />
        <strong>{title}</strong>
      </div>
      {hasItems ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </div>
  );
}

function MarginChart({ test }) {
  const rows = test.summary ?? [];
  const max = Math.max(...rows.map((row) => Math.max(Number(row.margem_por_comprador), 0)), 1);

  return (
    <div className="chart" role="img" aria-label="Grafico de margem por comprador por variante">
      {rows.map((row) => {
        const tone = getVariantTone(test, row);
        const width = `${Math.max((Number(row.margem_por_comprador) / max) * 100, 1)}%`;
        return (
          <div className="chart-row" key={row.variante}>
            <div className="chart-label">
              <span>
                <StatusIcon tone={tone} />
                {row.variante}
              </span>
              <strong>{moneyFormatter.format(row.margem_por_comprador)}</strong>
            </div>
            <div className="bar-track">
              <div className={`bar ${tone}`} style={{ width }} />
            </div>
            <small>{toneLabel(tone)}</small>
          </div>
        );
      })}
    </div>
  );
}

function SummaryTable({ test }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Variante</th>
            <th>Compradores</th>
            <th>Vendas</th>
            <th>Cashback</th>
            <th>Margem total</th>
            <th>Margem/comprador</th>
            <th>Ticket medio</th>
            <th>Cashback/vendas</th>
            <th>ROI</th>
          </tr>
        </thead>
        <tbody>
          {(test.summary ?? []).map((row) => {
            const tone = getVariantTone(test, row);
            return (
              <tr key={row.variante} className={tone}>
                <td>
                  <span className={`status-text ${tone}`}>
                    <StatusIcon tone={tone} />
                    {row.variante} · {toneLabel(tone)}
                  </span>
                </td>
                <td>{numberFormatter.format(row.compradores_total)}</td>
                <td>{compactMoneyFormatter.format(row.vendas_total)}</td>
                <td>{compactMoneyFormatter.format(row.cashback_total)}</td>
                <td>{moneyFormatter.format(row.margem_total)}</td>
                <td><strong>{moneyFormatter.format(row.margem_por_comprador)}</strong></td>
                <td>{moneyFormatter.format(row.ticket_medio)}</td>
                <td>{decimalFormatter.format(row.cashback_pct_vendas)}%</td>
                <td>{decimalFormatter.format(row.roi_cashback)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ComparisonTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Variante</th>
            <th>Baseline</th>
            <th>Dif. margem/comprador</th>
            <th>IC95</th>
            <th>Prob. supera baseline</th>
            <th>Dias</th>
            <th>Bootstrap</th>
            <th>Amostra</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.variante}-${row.vs_baseline}`}>
              <td>{row.variante}</td>
              <td>{row.vs_baseline}</td>
              <td><strong>{moneyFormatter.format(row.dif_margem_por_comprador_media)}</strong></td>
              <td>
                {moneyFormatter.format(row.ic95_low)} a {moneyFormatter.format(row.ic95_high)}
              </td>
              <td>{percentFormatter.format(row.prob_variante_supera_baseline)}</td>
              <td>
                {row.n_dias_variante} / {row.n_dias_baseline}
              </td>
              <td>
                <span className="status-text neutral">
                  <ShieldCheck size={17} weight="duotone" />
                  {row.pareamento_usado ? "Pareado" : "Independente"}
                </span>
              </td>
              <td>
                {row.amostra_pequena_lt30d ? (
                  <span className="status-text danger">
                    <Warning size={17} weight="duotone" />
                    Amostra pequena
                  </span>
                ) : (
                  <span className="status-text confirmed">
                    <CheckCircle size={17} weight="duotone" />
                    Suficiente
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
