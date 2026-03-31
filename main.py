"""Entry point – run with ``python main.py``."""

import logging

from src.copycat.bot import main

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()
