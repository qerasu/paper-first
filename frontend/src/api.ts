import type { BacktestJob, BacktestReport, StrategySpec } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
const POLL_ATTEMPTS = 60;
const POLL_INTERVAL_MS = 1000;

export async function runBacktest(strategy: StrategySpec): Promise<BacktestReport> {
  const job = await startBacktest(strategy);
  for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt += 1) {
    const currentJob = attempt === 0 ? job : await fetchBacktestJob(job.id);
    if (currentJob.status === "completed") {
      if (!currentJob.report) {
        throw new Error("Backtest finished without a report");
      }
      return currentJob.report;
    }
    if (currentJob.status === "failed") {
      throw new Error(currentJob.error ?? "Backtest failed");
    }

    await sleep(POLL_INTERVAL_MS);
  }

  throw new Error("Backtest timed out");
}


export async function importStrategy(input: { text: string; file: File | null }): Promise<StrategySpec> {
  const body = new FormData();
  if (input.text.trim()) {
    body.append("text", input.text);
  }
  if (input.file) {
    body.append("file", input.file);
  }

  const response = await fetch(`${API_BASE_URL}/strategy/import`, {
    method: "POST",
    body
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? "Strategy import failed");
  }
  return response.json();
}


async function startBacktest(strategy: StrategySpec): Promise<BacktestJob> {
  const response = await fetch(`${API_BASE_URL}/backtests/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      strategy,
      candles: [],
      use_demo_data: true
    })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? "Backtest did not start");
  }
  return response.json();
}


async function fetchBacktestJob(id: string): Promise<BacktestJob> {
  const response = await fetch(`${API_BASE_URL}/backtests/${id}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? "Backtest status is unavailable");
  }
  return response.json();
}


function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
