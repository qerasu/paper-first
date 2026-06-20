export type Verdict = "reject" | "unstable" | "research" | "paper" | "live-ready";

export type SignalCondition = {
  left: string;
  operator: ">" | ">=" | "<" | "<=" | "==" | "!=";
  right: number | string;
};

export type SignalGroup = {
  all?: SignalCondition[];
  any?: SignalCondition[];
};

export type StrategySpec = {
  name: string;
  symbol: string;
  timeframe: string;
  entry: SignalGroup;
  exit: SignalGroup;
  risk: {
    initial_capital: number;
    position_size_pct: number;
    stop_loss_pct?: number | null;
    take_profit_pct?: number | null;
    fee_bps: number;
    slippage_bps: number;
    max_drawdown_pct: number;
  };
  metadata?: Record<string, unknown>;
};

export type BacktestReport = {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  verdict: Verdict;
  verdict_reason: string;
  metrics: {
    total_candles: number;
    trade_count: number;
    net_profit: number;
    net_profit_pct: number;
    max_drawdown_pct: number;
    win_rate_pct: number;
    profit_factor: number | null;
    expectancy_pct: number;
    fees_paid: number;
  };
  trades: Array<{
    entry_time: string;
    exit_time: string;
    entry_price: number;
    exit_price: number;
    quantity: number;
    gross_pnl: number;
    net_pnl: number;
    fees_paid: number;
    return_pct: number;
    exit_reason: string;
  }>;
  equity_curve: Array<{
    timestamp: string;
    equity: number;
    drawdown_pct: number;
  }>;
  warnings: string[];
};
