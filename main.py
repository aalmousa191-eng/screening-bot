"""Entry point: start Telegram bot with APScheduler."""
import logging
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


async def post_init(app: Application) -> None:
    """Called by run_polling() after initialize() and start() — safe to use the bot here."""
    await set_bot_commands(app)
    scheduler = create_scheduler(app)
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info(
        "Scheduler started. Screener: %s | Brief: %s",
        [str(j.next_run_time) for j in scheduler.get_jobs() if j.id == "daily_screener"],
        [str(j.next_run_time) for j in scheduler.get_jobs() if j.id == "morning_brief"],
    )
    logger.info("Bot is running. Send /start to your bot on Telegram.")


async def post_shutdown(app: Application) -> None:
    """Called by run_polling() during shutdown."""
    scheduler = app.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    logger.info("Starting AI Stock Analysis Bot…")
    app = create_application(post_init=post_init, post_shutdown=post_shutdown)
    # run_polling() handles: initialize → start → poll → stop → shutdown
    app.run_polling(drop_pending_updates=True)
    logger.info("Bot stopped.")
