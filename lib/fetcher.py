#!/usr/bin/env python3
"""
Polymarket API fetcher — Gamma (public) + CLOB (authenticated)
"""
import time
import requests
from typing import Optional
import json
import os

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

# ─── Gamma (public) ──────────────────────────────────────────────────────────

def get_markets(
    limit: int = 200,
    category: Optional[str] = None,
    closed: bool = False,
) -> list[dict]:
    """Fetch markets from Gamma API."""
    params = {"limit": limit}
    if category:
        params["category"] = category
    if closed:
        params["closed"] = "true"

    resp = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_market_by_slug(slug: str) -> Optional[dict]:
    """Fetch single market by slug."""
    resp = requests.get(f"{GAMMA_BASE}/markets", params={"slug": slug}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data[0] if data else None


def get_trending(limit: int = 20) -> list[dict]:
    """Top markets by 24h volume."""
    markets = get_markets(limit=limit)
    return sorted(markets, key=lambda m: float(m.get("volume24hr", 0) or 0), reverse=True)


def get_sports_markets(sport: str = "Soccer", limit: int = 50) -> list[dict]:
    """Sports markets, optionally filtered by sport tag."""
    markets = get_markets(limit=limit * 2)
    sports = [m for m in markets if sport.lower() in (m.get("tags", []) or []).lower()]
    return sports[:limit]


def get_crypto_markets(limit: int = 30) -> list[dict]:
    """Crypto-related markets."""
    markets = get_markets(limit=limit * 2)
    crypto = [m for m in markets if "crypto" in (m.get("tags", []) or "").lower()]
    return crypto[:limit]


def get_closing_soon(hours: int = 24, limit: int = 20) -> list[dict]:
    """Markets closing within N hours."""
    markets = get_markets(limit=500)
    now = time.time()
    cutoff = now + hours * 3600
    return [
        m for m in markets
        if m.get("endTime")
        and now < _parse_ts(m["endTime"]) < cutoff
    ][:limit]


# ─── CLOB (authenticated) ───────────────────────────────────────────────────

def get_positions(clob_client) -> list[dict]:
    """Get filled trades/positions from CLOB."""
    try:
        trades = clob_client.get_trades()
        return trades or []
    except Exception as e:
        print(f"[fetcher] get_positions error: {e}")
        return []


def get_open_orders(clob_client) -> list[dict]:
    """Get pending orders from CLOB."""
    try:
        orders = clob_client.get_orders()
        return orders or []
    except Exception as e:
        print(f"[fetcher] get_open_orders error: {e}")
        return []


def get_cash_balance(wallet: str, rpc_url: str) -> Optional[float]:
    """Get USDC.e balance on EOA via web3."""
    try:
        from web3 import Web3
        USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        abi = [
            {
                "inputs": [{"name": "a", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        c = w3.eth.contract(
            address=Web3.to_checksum_address(USDC_CONTRACT),
            abi=abi,
        )
        bal = c.functions.balanceOf(Web3.to_checksum_address(wallet)).call()
        return bal / 1e6
    except Exception as e:
        print(f"[fetcher] get_cash_balance error: {e}")
        return None


def get_clob_balance(clob_client) -> Optional[float]:
    """Get CLOB collateral balance."""
    try:
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        result = clob_client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return int(result.get("balance", 0)) / 1e6
    except Exception as e:
        print(f"[fetcher] get_clob_balance error: {e}")
        return None


# ─── Market name cache ────────────────────────────────────────────────────────

_TOKEN_CACHE: dict[str, str] = {}
_COND_CACHE: dict[str, str] = {}


def build_token_cache(markets: list[dict]):
    """Pre-populate token->name cache from market list."""
    for m in markets:
        for tid in m.get("clobTokenIds", []) or []:
            _TOKEN_CACHE[tid] = m.get("question", "Unknown")
        cid = m.get("conditionId", "")
        if cid:
            _COND_CACHE[cid] = m.get("question", "Unknown")


def lookup_name(asset_id: str = "", condition_id: str = "") -> str:
    """Fast cache lookup for market name."""
    if asset_id and asset_id in _TOKEN_CACHE:
        return _TOKEN_CACHE[asset_id]
    if condition_id and condition_id in _COND_CACHE:
        return _COND_CACHE[condition_id]
    # fallback: live lookup
    if asset_id:
        for tid, name in _TOKEN_CACHE.items():
            if tid == asset_id:
                return name
    return "Unknown"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_ts(ts: str) -> float:
    """Parse ISO timestamp to epoch."""
    try:
        return time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0
