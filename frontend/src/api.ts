import type { BacktestReport, StrategySpec } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export async function fetchSampleStrategy(): Promise<StrategySpec> {
  const response = await fetch(`${API_BASE_URL}/strategy/sample`);
  if (!response.ok) {
    throw new Error("Не удалось получить пример стратегии");
  }
  return response.json();
}

export async function runBacktest(strategy: StrategySpec): Promise<BacktestReport> {
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
    throw new Error(payload.detail ?? "Бэктест не запустился");
  }
  return response.json();
}
