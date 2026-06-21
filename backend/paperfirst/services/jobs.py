from uuid import UUID

from paperfirst.domain.backtest import BacktestRunRequest


QUEUE_NAME = "backtests"


def enqueue_backtest(backtest_id: UUID, request: BacktestRunRequest, redis_url: str) -> str:
    from redis import Redis
    from rq import Queue

    connection = Redis.from_url(redis_url)
    queue = Queue(QUEUE_NAME, connection=connection)
    job = queue.enqueue(
        "paperfirst.worker.tasks.run_backtest_job",
        {"backtest_id": str(backtest_id), "request": request.model_dump(mode="json")},
    )
    return job.id
