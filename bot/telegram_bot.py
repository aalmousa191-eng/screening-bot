"""Telegram bot: command handlers and message utilities."""
import asyncio
import logging
from datetime import datetime
from functools import wraps
from typing import Callable

import pytz
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

from data.polygon_client import PolygonClient
from analysis.technical import calculate_indicators, build_snapshot, format_technical_report
from analysis.fundamental import parse_fundamentals, format_fundamental_report
from analysis.market_movers import get_market_overview, format_movers_report
from analysis.screener import run_screener, format_screener_report
from ai.claude_analyst import analyze_stock, quick_analysis, generate_morning_brief
from utils.formatters import split_message
from config import config

logger = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")

# Shared cache for screener results (populated by scheduler)
_screener_cache: list = []
_overview_cache = None


def _set_screener_cache(results: list) -> None:
    global _screener_cache
    _screener_cache = results


def _set_overview_cache(overview) -> None:
    global _overview_cache
    _overview_cache = overview


def _get_screener_cache() -> list:
    return _screener_cache


def _get_overview_cache():
    return _overview_cache


# ── Auth middleware ───────────────────────────────────────────────────────────

def restricted(func: Callable) -> Callable:
    """Decorator: only allow messages from allowed chat IDs."""
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        cid = update.effective_chat.id if update.effective_chat else None
        if config.ALLOWED_CHAT_IDS and cid not in config.ALLOWED_CHAT_IDS:
            logger.warning("Unauthorized access attempt from chat %s", cid)
            if update.message:
                await update.message.reply_text("⛔ Unauthorized.")
            return
        await func(update, ctx)
    return wrapper


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send_long(update: Update, text: str, parse_mode: str = ParseMode.HTML) -> None:
    """Send a potentially long message, splitting if needed."""
    for chunk in split_message(text):
        await update.message.reply_text(chunk, parse_mode=parse_mode)
        await asyncio.sleep(0.3)


async def _typing(update: Update) -> None:
    await update.message.reply_chat_action("typing")


# ── Command handlers ──────────────────────────────────────────────────────────

@restricted
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 <b>Welcome to your AI Stock Analysis Bot!</b>\n\n"
        "Powered by <b>Polygon.io</b> market data and <b>Claude Opus AI</b>.\n\n"
        "<b>Available Commands:</b>\n"
        "/analyze &lt;TICKER&gt; — Full fundamental + technical + AI analysis\n"
        "/technical &lt;TICKER&gt; — Technical indicators and chart signals\n"
        "/fundamental &lt;TICKER&gt; — Valuation, financials, and quality metrics\n"
        "/movers — Top gainers, losers, and most active stocks\n"
        "/screen — Run screener: top 20 stocks to watch\n"
        "/brief — Generate today's morning market brief\n"
        "/status — Bot and market status\n"
        "/help — Show this message\n\n"
        "📅 <b>Daily Automation:</b>\n"
        f"• Screener runs at {config.SCREENER_HOUR:02d}:{config.SCREENER_MINUTE:02d} ET\n"
        f"• Morning brief at {config.MORNING_BRIEF_HOUR:02d}:{config.MORNING_BRIEF_MINUTE:02d} ET\n\n"
        "Example: <code>/analyze NVDA</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


@restricted
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, ctx)


@restricted
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _typing(update)
    now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")
    cache_status = f"✅ {len(_screener_cache)} stocks" if _screener_cache else "⏳ Not yet run"
    async with PolygonClient() as client:
        status_data = await client.get_market_status()
    market = status_data.get("market", "unknown")
    emoji = {"open": "🟢", "closed": "🔴", "extended-hours": "🟡"}.get(market, "⚪")
    text = (
        f"<b>🤖 Bot Status</b>\n\n"
        f"Time:          {now_et}\n"
        f"Market:        {emoji} {market.upper()}\n"
        f"Screener cache: {cache_status}\n"
        f"Model:         Claude Opus 4.6\n"
        f"Data source:   Polygon.io"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


@restricted
async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Full AI-powered analysis: technical + fundamental + Claude narrative."""
    ticker = _parse_ticker(ctx.args)
    if not ticker:
        await update.message.reply_text("Usage: /analyze &lt;TICKER&gt;\nExample: /analyze AAPL", parse_mode=ParseMode.HTML)
        return

    await _typing(update)
    msg = await update.message.reply_text(f"🔍 Analyzing <b>{ticker}</b>… This may take 20-30 seconds.", parse_mode=ParseMode.HTML)

    try:
        async with PolygonClient() as client:
            df, details, financials, snap = await asyncio.gather(
                client.get_aggregates(ticker, days=365),
                client.get_ticker_details(ticker),
                client.get_financials(ticker, limit=4),
                client.get_ticker_snapshot(ticker),
            )

        if df.empty:
            await msg.edit_text(f"❌ No data found for <b>{ticker}</b>. Check the ticker symbol.", parse_mode=ParseMode.HTML)
            return

        price = float(snap.get("day", {}).get("c") or df["close"].iloc[-1])

        # Technical
        df_ind = calculate_indicators(df)
        tech = build_snapshot(ticker, df_ind)

        # Fundamental
        fund = parse_fundamentals(ticker, details, financials, price)

        # Headers
        tech_report = format_technical_report(tech)
        fund_report = format_fundamental_report(fund)

        # AI narrative
        await msg.edit_text(f"🤖 Generating AI analysis for <b>{ticker}</b>…", parse_mode=ParseMode.HTML)
        ai_narrative = await analyze_stock(ticker, tech, fund, details)

        # Send reports
        await msg.delete()
        await _send_long(update, tech_report)
        await _send_long(update, fund_report)
        ai_header = f"<b>🧠 AI ANALYST VIEW — {ticker}</b>\n\n"
        await _send_long(update, ai_header + ai_narrative)

    except Exception as e:
        logger.exception("Error in /analyze %s", ticker)
        await msg.edit_text(f"❌ Error analyzing {ticker}: {e}")


@restricted
async def cmd_technical(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Technical analysis only."""
    ticker = _parse_ticker(ctx.args)
    if not ticker:
        await update.message.reply_text("Usage: /technical &lt;TICKER&gt;", parse_mode=ParseMode.HTML)
        return

    await _typing(update)
    msg = await update.message.reply_text(f"📊 Fetching technical data for <b>{ticker}</b>…", parse_mode=ParseMode.HTML)

    try:
        async with PolygonClient() as client:
            df = await client.get_aggregates(ticker, days=365)

        if df.empty:
            await msg.edit_text(f"❌ No data found for <b>{ticker}</b>.", parse_mode=ParseMode.HTML)
            return

        df_ind = calculate_indicators(df)
        tech = build_snapshot(ticker, df_ind)
        report = format_technical_report(tech)
        await msg.delete()
        await _send_long(update, report)
    except Exception as e:
        logger.exception("Error in /technical %s", ticker)
        await msg.edit_text(f"❌ Error: {e}")


@restricted
async def cmd_fundamental(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Fundamental analysis only."""
    ticker = _parse_ticker(ctx.args)
    if not ticker:
        await update.message.reply_text("Usage: /fundamental &lt;TICKER&gt;", parse_mode=ParseMode.HTML)
        return

    await _typing(update)
    msg = await update.message.reply_text(f"📈 Fetching fundamental data for <b>{ticker}</b>…", parse_mode=ParseMode.HTML)

    try:
        async with PolygonClient() as client:
            details, financials, snap = await asyncio.gather(
                client.get_ticker_details(ticker),
                client.get_financials(ticker, limit=4),
                client.get_ticker_snapshot(ticker),
            )

        price = float(snap.get("day", {}).get("c") or 0)
        fund = parse_fundamentals(ticker, details, financials, price)
        report = format_fundamental_report(fund)
        await msg.delete()
        await _send_long(update, report)
    except Exception as e:
        logger.exception("Error in /fundamental %s", ticker)
        await msg.edit_text(f"❌ Error: {e}")


@restricted
async def cmd_movers(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Market movers: gainers, losers, most active + indices + sectors."""
    await _typing(update)
    msg = await update.message.reply_text("📊 Fetching market movers…")

    try:
        async with PolygonClient() as client:
            overview = await get_market_overview(client)

        report = format_movers_report(overview)
        await msg.delete()
        await _send_long(update, report)
    except Exception as e:
        logger.exception("Error in /movers")
        await msg.edit_text(f"❌ Error fetching movers: {e}")


@restricted
async def cmd_screen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Run stock screener or return cached results."""
    cached = _get_screener_cache()
    if cached:
        report = format_screener_report(cached)
        header = "<b>🔍 SCREENER RESULTS (cached)</b>\n\n"
        await _send_long(update, header + report)
        return

    await _typing(update)
    msg = await update.message.reply_text(
        "🔍 Running full screener on ~100 stocks… This takes 1-2 minutes. Please wait."
    )

    try:
        async with PolygonClient() as client:
            results = await run_screener(client)
        _set_screener_cache(results)
        report = format_screener_report(results)
        await msg.delete()
        await _send_long(update, report)
    except Exception as e:
        logger.exception("Error in /screen")
        await msg.edit_text(f"❌ Screener error: {e}")


@restricted
async def cmd_brief(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate morning brief on demand."""
    await _typing(update)
    msg = await update.message.reply_text("📝 Generating morning brief… Please wait (30-60s).")

    try:
        async with PolygonClient() as client:
            overview = await get_market_overview(client)
        _set_overview_cache(overview)

        top_stocks = _get_screener_cache()
        if not top_stocks:
            await msg.edit_text("⏳ Running screener first… This may take 1-2 minutes.")
            async with PolygonClient() as client:
                top_stocks = await run_screener(client)
            _set_screener_cache(top_stocks)

        await msg.edit_text("🤖 Claude is writing the brief…")
        date_str = datetime.now(ET).strftime("%A, %B %d, %Y")
        narrative = await generate_morning_brief(overview, top_stocks, date_str)

        # Format the full brief
        from analysis.market_movers import format_movers_report
        movers_section = format_movers_report(overview)

        screener_section = format_screener_report(top_stocks[:10])  # top 10 for brief

        brief_header = (
            f"🌅 <b>MORNING MARKET BRIEF</b>\n"
            f"<b>{date_str}</b>\n"
            f"{'─' * 30}\n\n"
        )
        ai_section = f"\n\n<b>🧠 ANALYST COMMENTARY</b>\n\n{narrative}"

        await msg.delete()
        await _send_long(update, brief_header + movers_section)
        await _send_long(update, screener_section)
        await _send_long(update, ai_section)

    except Exception as e:
        logger.exception("Error in /brief")
        await msg.edit_text(f"❌ Error generating brief: {e}")


# ── Application factory ───────────────────────────────────────────────────────

def create_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("technical", cmd_technical))
    app.add_handler(CommandHandler("fundamental", cmd_fundamental))
    app.add_handler(CommandHandler("movers", cmd_movers))
    app.add_handler(CommandHandler("screen", cmd_screen))
    app.add_handler(CommandHandler("brief", cmd_brief))

    return app


async def set_bot_commands(app: Application) -> None:
    commands = [
        BotCommand("analyze", "Full AI analysis for a ticker"),
        BotCommand("technical", "Technical indicators for a ticker"),
        BotCommand("fundamental", "Fundamental analysis for a ticker"),
        BotCommand("movers", "Top gainers, losers & most active"),
        BotCommand("screen", "Top 20 stocks to watch (screener)"),
        BotCommand("brief", "Generate today's morning brief"),
        BotCommand("status", "Bot and market status"),
        BotCommand("help", "Show all commands"),
    ]
    await app.bot.set_my_commands(commands)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_ticker(args: list[str] | None) -> str | None:
    if not args:
        return None
    t = args[0].upper().strip()
    return t if t.isalpha() and len(t) <= 5 else None
