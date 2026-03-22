"""APScheduler jobs for daily screener and morning brief."""
import asyncio
import logging
from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.constants import ParseMode
from telegram.ext import Application

from data.polygon_client import PolygonClient
from analysis.market_movers import get_market_overview, format_movers_report
from analysis.screener import run_screener, format_screener_report
from ai.claude_analyst import generate_morning_brief
from bot.telegram_bot import (
    _set_screener_cache,
    _set_overview_cache,
    _get_screener_cache,
)
from utils.formatters import split_message
from config import config

logger = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")


async def _send_to_all(app: Application, text: str, parse_mode: str = ParseMode.HTML) -> None:
    """Send a message to all allowed chat IDs."""
    for cid in config.ALLOWED_CHAT_IDS:
        try:
            for chunk in split_message(text):
                await app.bot.send_message(chat_id=cid, text=chunk, parse_mode=parse_mode)
                await asyncio.sleep(0.3)
        except Exception as e:
            logger.error("Failed to send to chat %s: %s", cid, e)


async def job_run_screener(app: Application) -> None:
    """Scheduled job: run the screener and cache results."""
    logger.info("Scheduled screener job starting…")
    try:
        async with PolygonClient() as client:
            results = await run_screener(client)
        _set_screener_cache(results)
        logger.info("Screener complete: %d results cached", len(results))
    except Exception as e:
        logger.error("Scheduled screener job failed: %s", e)


async def job_morning_brief(app: Application) -> None:
    """Scheduled job: fetch market data, generate AI brief, send to all chats."""
    logger.info("Morning brief job starting…")
    try:
        async with PolygonClient() as client:
            overview = await get_market_overview(client)
        _set_overview_cache(overview)

        top_stocks = _get_screener_cache()
        if not top_stocks:
            logger.info("No screener cache, running screener now…")
            async with PolygonClient() as client:
                top_stocks = await run_screener(client)
            _set_screener_cache(top_stocks)

        date_str = datetime.now(ET).strftime("%A, %B %d, %Y")
        narrative = await generate_morning_brief(overview, top_stocks, date_str)

        movers_section = format_movers_report(overview)
        screener_section = format_screener_report(top_stocks[:10])

        brief_header = (
            f"🌅 <b>MORNING MARKET BRIEF</b>\n"
            f"<b>{date_str}</b>\n"
            f"{'─' * 30}\n\n"
        )
        ai_section = f"\n\n<b>🧠 ANALYST COMMENTARY</b>\n\n{narrative}"

        await _send_to_all(app, brief_header + movers_section)
        await asyncio.sleep(1)
        await _send_to_all(app, screener_section)
        await asyncio.sleep(1)
        await _send_to_all(app, ai_section)

        logger.info("Morning brief sent successfully")
    except Exception as e:
        logger.error("Morning brief job failed: %s", e)
        await _send_to_all(app, f"⚠️ Morning brief failed: {e}")


def create_scheduler(app: Application) -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(timezone=ET)

    # Run screener before the brief
    scheduler.add_job(
        job_run_screener,
        trigger="cron",
        hour=config.SCREENER_HOUR,
        minute=config.SCREENER_MINUTE,
        args=[app],
        id="daily_screener",
        name="Daily Stock Screener",
        replace_existing=True,
    )

    # Morning brief
    scheduler.add_job(
        job_morning_brief,
        trigger="cron",
        hour=config.MORNING_BRIEF_HOUR,
        minute=config.MORNING_BRIEF_MINUTE,
        args=[app],
        id="morning_brief",
        name="Daily Morning Brief",
        replace_existing=True,
    )

    return scheduler
