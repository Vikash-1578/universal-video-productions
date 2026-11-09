"""Run the Telegram bot:  python -m app.bot"""
from __future__ import annotations
import logging
import sys

from app.bot.telegram_bot import StudioBot
from app.core.config import load_settings
from app.hub import Hub


def main() -> int:
    settings = load_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # PTB polls constantly; keep the log readable
    if not settings.bot_token:
        print("Set BOT_TOKEN (or TELEGRAM_BOT_TOKEN) in .env first. Get one from @BotFather.", file=sys.stderr)
        return 1
    bot = StudioBot(Hub(settings))
    if bot.setup_mode:
        logging.warning("No allowed users configured: running in setup mode. Message the bot to get your "
                        "user ID, then set OWNER_ID in .env and restart.")
    bot.build_application(settings.bot_token).run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
