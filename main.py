"""Entry point: start Telegram bot with APScheduler."""
import asyncio
import logging
import signal
import sys

from telegram.ext import Application

from bot.telegram_bot import create_application, set_bot_commands
from bot.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting AI Stock Analysis Bot…")

    app: Application = create_application()
    scheduler = create_scheduler(app)

    async with app:
        await set_bot_commands(app)
        scheduler.start()
        logger.info(
            "Scheduler started. Screener: %s, Brief: %s",
            [str(j.next_run_time) for j in scheduler.get_jobs() if j.id == "daily_screener"],
            [str(j.next_run_time) for j in scheduler.get_jobs() if j.id == "morning_brief"],
        )
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot is running. Press Ctrl+C to stop.")

        # Keep running until SIGINT/SIGTERM
        stop_event = asyncio.Event()

        def _stop(*_):
            logger.info("Shutdown signal received")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _stop)

        await stop_event.wait()

        logger.info("Shutting down…")
        scheduler.shutdown(wait=False)
        await app.updater.stop()

    logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
