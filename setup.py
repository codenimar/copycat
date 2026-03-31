"""
Copycat – Binance Copy-Trading Bot
===================================
Automatically mirrors the best-performing traders from the Binance Leaderboard
onto a Binance Futures account, with position sizes scaled to the user's bankroll.
"""

from setuptools import setup, find_packages

setup(
    name="copycat",
    version="0.1.0",
    description="Binance copy-trading bot that mirrors top traders",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "python-binance>=1.0.19",
        "python-dotenv>=1.0.1",
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": ["pytest>=8.1.1", "pytest-mock>=3.14.0"],
    },
    entry_points={
        "console_scripts": [
            "copycat=copycat.bot:main",
        ],
    },
)
