#!/usr/bin/env python3
"""
Portfolio analysis — P&L, allocation, win rate
"""
from typing import Optional
from dataclasses import dataclass, field

@dataclass
class Position:
    market_name: str
    side: str          # BUY / SELL
    size: float         # number of shares
    price: float        # avg fill price
    asset_id: str
    condition_id: str = ""
    current_price: float = 0.0
    outcome: str = ""

    @property
    def cost(self) -> float:
        return self.size * self.price

    @property
    def max_payout(self) -> float:
        """If YES: payout = size (at $1). If NO: same."""
        return self.size

    @property
    def pnl(self) -> float:
        """PnL if resolved YES (for YES positions)."""
        if self.side == "BUY":
            return (self.current_price - self.price) * self.size
        else:
            return (self.price - self.current_price) * self.size

    @property
    def pnl_pct(self) -> float:
        if self.price == 0:
            return 0.0
        return ((self.current_price - self.price) / self.price) * 100

    @property
    def current_value(self) -> float:
        if self.side == "BUY":
            return self.current_price * self.size
        return self.cost - (self.price - self.current_price) * self.size


def parse_trades(trades: list[dict]) -> list[Position]:
    """Convert raw CLOB trades into Position objects."""
    positions = []
    for t in trades:
        p = Position(
            market_name=t.get("market_name", "Unknown"),
            side=t.get("side", "BUY").upper(),
            size=float(t.get("size", 0)),
            price=float(t.get("price", 0)),
            asset_id=t.get("asset_id", ""),
            condition_id=t.get("market", ""),
            current_price=float(t.get("price", 0)),  # will be updated
            outcome=t.get("outcome", ""),
        )
        positions.append(p)
    return positions


def calculate_portfolio_metrics(
    positions: list[Position],
    cash: float,
) -> dict:
    """Aggregate portfolio stats."""
    if not positions:
        return {
            "total_invested": 0,
            "total_current_value": cash,
            "total_pnl": 0,
            "win_rate": 0,
            "position_count": 0,
            "by_market": {},
        }

    invested = sum(p.cost for p in positions)
    current_val = sum(p.current_value for p in positions)
    total_assets = invested + cash

    wins = sum(1 for p in positions if p.pnl > 0)
    win_rate = (wins / len(positions) * 100) if positions else 0

    return {
        "total_invested": invested,
        "total_current_value": current_val + cash,
        "total_pnl": current_val - invested,
        "cash": cash,
        "win_rate": win_rate,
        "position_count": len(positions),
        "total_positions_value": current_val,
        "by_market": {p.market_name: p for p in positions},
    }


def build_allocation(positions: list[Position], cash: float) -> dict:
    """Build allocation breakdown for pie chart."""
    total = sum(p.current_value for p in positions) + cash
    allocation = {}
    if cash > 0:
        allocation["💵 Cash"] = cash
    for p in positions:
        name = p.market_name[:40] + ("..." if len(p.market_name) > 40 else "")
        allocation[name] = p.current_value
    return allocation


def format_currency(amount: float) -> str:
    return f"${abs(amount):,.2f}"


def format_pnl(amount: float) -> str:
    emoji = "📈" if amount >= 0 else "📉"
    return f"{emoji} {format_currency(amount)}"
