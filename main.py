from __future__ import annotations

from afk_bot.bot import AFKBot
from afk_bot.config import load_settings



def main() -> None:
    settings = load_settings()
    bot = AFKBot(settings)
    bot.run(settings.token)


if __name__ == "__main__":
    main()
