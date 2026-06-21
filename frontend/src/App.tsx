import { AlertTriangle, CheckCircle2, Play, RefreshCw, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchSampleStrategy, runBacktest } from "./api";
import { initTelegramWebApp } from "./telegram";
import type { BacktestReport, StrategySpec, Verdict } from "./types";

const verdictLabels: Record<Verdict, string> = {
  reject: "reject",
  unstable: "unstable",
  research: "research",
  paper: "paper",
  "live-ready": "live-ready"
};

function App() {
  const [strategyText, setStrategyText] = useState("");
  const [report, setReport] = useState<BacktestReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    initTelegramWebApp();
    fetchSampleStrategy()
      .then((strategy) => setStrategyText(JSON.stringify(strategy, null, 2)))
      .catch((fetchError) => setError(fetchError instanceof Error ? fetchError.message : "Unknown error"));
  }, []);

  const parsedStrategy = useMemo(() => {
    try {
      return JSON.parse(strategyText) as StrategySpec;
    } catch {
      return null;
    }
  }, [strategyText]);

  const handleRun = async () => {
    if (!parsedStrategy) {
      setError("Strategy JSON is invalid");
      return;
    }

    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const nextReport = await runBacktest(parsedStrategy);
      setReport(nextReport);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Paper First</p>
            <h1>Pre-deposit strategy audit</h1>
          </div>
          <button className="primaryButton" disabled={loading || !parsedStrategy} onClick={handleRun}>
            {loading ? <RefreshCw className="spin" size={18} /> : <Play size={18} />}
            Run demo audit
          </button>
        </header>

        <div className="grid">
          <section className="editorPanel">
            <div className="panelHeader">
              <div>
                <h2>StrategySpec</h2>
                <span>{parsedStrategy ? "valid JSON" : "JSON error"}</span>
              </div>
              {parsedStrategy ? <CheckCircle2 size={20} /> : <ShieldAlert size={20} />}
            </div>
            <textarea
              spellCheck={false}
              value={strategyText}
              onChange={(event) => setStrategyText(event.target.value)}
            />
          </section>

          <section className="reportPanel">
            {error ? (
              <div className="notice danger">
                <AlertTriangle size={20} />
                <span>{error}</span>
              </div>
            ) : null}

            {report ? <ReportView report={report} /> : <EmptyReport />}
          </section>
        </div>
      </section>
    </main>
  );
}


function EmptyReport() {
  return (
    <div className="emptyState">
      <ShieldAlert size={32} />
      <h2>The report will appear after launch</h2>
      <p>The MVP uses built-in demo candle history to test the pipeline without connecting an exchange.</p>
    </div>
  );
}


function ReportView({ report }: { report: BacktestReport }) {
  return (
    <div className="reportStack">
      <div className={`verdict verdict-${report.verdict}`}>
        <span>{verdictLabels[report.verdict]}</span>
        <strong>{report.verdict_reason}</strong>
      </div>

      <div className="metricsGrid">
        <Metric label="Net PnL" value={`${report.metrics.net_profit_pct.toFixed(2)}%`} />
        <Metric label="Max DD" value={`${report.metrics.max_drawdown_pct.toFixed(2)}%`} />
        <Metric label="Trades" value={String(report.metrics.trade_count)} />
        <Metric label="Winrate" value={`${report.metrics.win_rate_pct.toFixed(1)}%`} />
        <Metric label="PF" value={report.metrics.profit_factor?.toFixed(2) ?? "inf"} />
        <Metric label="Fees" value={`$${report.metrics.fees_paid.toFixed(2)}`} />
      </div>

      <EquityChart report={report} />

      {report.warnings.length > 0 ? (
        <div className="notice warning">
          <AlertTriangle size={20} />
          <span>{report.warnings.join(", ")}</span>
        </div>
      ) : null}

      <div className="tradeTable">
        <div className="tableHead">
          <span>Exit</span>
          <span>Return</span>
          <span>Net PnL</span>
        </div>
        {report.trades.slice(-8).map((trade) => (
          <div className="tableRow" key={`${trade.entry_time}-${trade.exit_time}`}>
            <span>{trade.exit_reason}</span>
            <span>{trade.return_pct.toFixed(2)}%</span>
            <span className={trade.net_pnl >= 0 ? "positive" : "negative"}>${trade.net_pnl.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}


function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


function EquityChart({ report }: { report: BacktestReport }) {
  const points = report.equity_curve;
  if (points.length < 2) {
    return null;
  }

  const width = 680;
  const height = 180;
  const minEquity = Math.min(...points.map((point) => point.equity));
  const maxEquity = Math.max(...points.map((point) => point.equity));
  const spread = Math.max(maxEquity - minEquity, 1);
  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((point.equity - minEquity) / spread) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <div className="chartPanel">
      <div className="chartHeader">
        <span>Equity curve</span>
        <strong>${points[points.length - 1].equity.toFixed(2)}</strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="equity curve">
        <path className="chartGrid" d={`M 0 ${height * 0.25} H ${width} M 0 ${height * 0.5} H ${width} M 0 ${height * 0.75} H ${width}`} />
        <path className="chartLine" d={path} />
      </svg>
    </div>
  );
}


export default App;
