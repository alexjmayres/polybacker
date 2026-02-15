"""Configuration management using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Wallet ---
    private_key: str = Field(default="", alias="POLYMARKET_PRIVATE_KEY")
    signature_type: int = Field(default=0, alias="POLYMARKET_SIGNATURE_TYPE")
    funder: Optional[str] = Field(default=None, alias="POLYMARKET_FUNDER")

    # --- Auth (Web3 Wallet Connect) ---
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_expiry_hours: int = Field(default=72, alias="JWT_EXPIRY_HOURS")

    # --- Copy Trading ---
    copy_percentage: float = Field(default=0.10, description="Fraction of original trade size to copy")
    min_copy_size: float = Field(default=5.0, description="Minimum copy size in USDC")
    max_copy_size: float = Field(default=100.0, description="Maximum copy size in USDC")
    max_daily_spend: float = Field(default=500.0, description="Maximum total USDC spend per day")
    max_trade_age: int = Field(default=300, description="Max trade age in seconds to still copy")
    order_mode: str = Field(default="limit", description="Order type: 'market' (FOK) or 'limit' (GTC with slippage cap)")
    max_slippage: float = Field(default=0.02, description="Max slippage vs trader's price for limit orders (0.02 = 2%)")

    # --- Arbitrage ---
    min_profit_pct: float = Field(default=1.0, description="Minimum profit % to trigger arbitrage")
    trade_amount: float = Field(default=10.0, description="USDC per arbitrage trade")
    max_position_size: float = Field(default=100.0, description="Max position size in USDC")

    # --- General ---
    poll_interval: int = Field(default=15, description="Seconds between polling cycles")
    auto_execute: bool = Field(default=True, description="Auto-execute trades vs dry-run")
    db_path: str = Field(default="polybacker.db", description="Path to SQLite database")

    # --- API URLs (rarely need changing) ---
    clob_host: str = Field(default="https://clob.polymarket.com")
    gamma_host: str = Field(default="https://gamma-api.polymarket.com")
    data_host: str = Field(default="https://data-api.polymarket.com")
    chain_id: int = Field(default=137)

    @field_validator("private_key")
    @classmethod
    def strip_0x_prefix(cls, v: str) -> str:
        """Strip 0x prefix if present — py-clob-client expects raw hex."""
        if v.startswith("0x") or v.startswith("0X"):
            return v[2:]
        return v

    @field_validator("funder", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


def load_settings(env_file: Optional[str] = None) -> Settings:
    """Load settings, optionally from a specific .env file path."""
    if env_file:
        return Settings(_env_file=env_file)
    return Settings()
