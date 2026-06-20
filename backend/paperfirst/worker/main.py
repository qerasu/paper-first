import logging

from redis import Redis
from rq import Worker

from paperfirst.core.config import get_settings
from paperfirst.services.jobs import QUEUE_NAME


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    worker = Worker([QUEUE_NAME], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
