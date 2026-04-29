"""
Crypto & Trading superpower pack — market structure, risk management, and execution.
"""
from __future__ import annotations

PACK = {
    "id": "crypto_trading",
    "title": "Crypto & Trading",
    "version": "1.0",
    "sections": {
        "market_structure": {
            "description": "Understanding how crypto markets are structured",
            "concepts": [
                {
                    "name": "Liquidity & Order Book",
                    "definition": "Bid/ask spread, market depth, slippage on large orders",
                    "rule": "Never market-buy >0.1% of 24h volume — slippage too high",
                },
                {
                    "name": "Funding Rate (Perps)",
                    "definition": "Periodic payment between longs and shorts to keep perp near spot",
                    "signal": "Extreme positive funding = overleveraged longs = potential long squeeze",
                },
                {
                    "name": "Open Interest",
                    "definition": "Total outstanding derivative contracts",
                    "signal": "Rising OI + rising price = strong trend; rising OI + falling price = distribution",
                },
                {
                    "name": "Exchange Flows",
                    "definition": "BTC/ETH flowing to exchanges (sell signal) vs to cold storage (accumulation)",
                },
                {
                    "name": "Dominance",
                    "definition": "BTC.D: rising = risk-off, capital rotating to BTC; falling = altseason",
                },
            ],
        },
        "risk_management": {
            "description": "The foundation of surviving in crypto",
            "rules": [
                "Never risk more than 1-2% of portfolio on a single trade",
                "Position size = (Account × Risk%) / (Entry - Stop Loss)",
                "Maximum 20-30% in any single asset",
                "Keep 10-20% in stablecoins for opportunities and emergencies",
                "Hardware wallet for >50% of holdings — not your keys, not your coins",
                "Never trade what you cannot afford to lose entirely",
            ],
            "portfolio_buckets": {
                "Core (60-70%)": "BTC + ETH — low volatility within crypto",
                "Growth (20-30%)": "Large-cap alts (top 20) with fundamentals",
                "Speculation (5-10%)": "Small caps, new narratives — assume 0 possible",
                "Stables (10-20%)": "USDC/DAI — DeFi yield or buying opportunities",
            },
        },
        "entry_frameworks": {
            "DCA": {
                "name": "Dollar Cost Averaging",
                "rule": "Fixed fiat amount on fixed schedule regardless of price",
                "best_for": "Long-term accumulation of BTC/ETH",
            },
            "Zone_Based": {
                "name": "Support/Resistance Zone Entry",
                "rule": "Identify key historical levels; scale in as price enters zone",
                "confirmation": "Wait for a bullish candle close before entering",
            },
            "Breakout": {
                "name": "Breakout Trading",
                "rule": "Enter on confirmed close above resistance + volume surge",
                "risk": "High false-breakout rate — position size smaller",
            },
        },
        "on_chain_metrics": {
            "items": [
                {"metric": "MVRV Z-Score", "description": "Market Cap / Realised Cap deviation", "signal": "Z>7 = historically overvalued"},
                {"metric": "NUPL", "description": "Net Unrealised Profit/Loss ratio", "signal": "Euphoria zone → distribution"},
                {"metric": "Puell Multiple", "description": "Miner revenue vs annual average", "signal": "Low = miner capitulation = buy zone"},
                {"metric": "SOPR", "description": "Spent Output Profit Ratio", "signal": "SOPR>1 = selling in profit; <1 = selling at loss"},
                {"metric": "Exchange Reserve", "description": "Total BTC on exchanges", "signal": "Declining = accumulation signal"},
            ],
        },
        "tax_and_compliance": {
            "principles": [
                "Every trade is a taxable event in most jurisdictions",
                "Track cost basis per transaction — FIFO or specific identification",
                "Staking rewards: taxed as income at receipt value",
                "Long-term holds (>1 year): reduced CGT rate in many jurisdictions",
                "Use crypto tax software (Koinly, CoinTracker, TokenTax)",
                "Keep records of all transactions — exchanges can go bankrupt",
            ],
        },
    },
    "quick_decisions": {
        "should_i_buy_now": [
            "Is this within my DCA plan? → execute",
            "Is this FOMO after a 30%+ run? → don't",
            "Is there genuine fundamental catalyst? → evaluate size",
            "Is my total crypto allocation already at max? → rebalance instead",
        ],
        "red_flags": [
            "Anonymous team + no code audit",
            "Unrealistic APY (>100% sustainable)",
            "Whitepaper without technical details",
            "No lock-up for team tokens",
            "Excessive influencer promotion",
        ],
    },
}


def get_pack() -> dict:
    return PACK


def position_size(account_value: float, risk_pct: float, entry: float, stop: float) -> float:
    """Calculate position size in quote currency."""
    if entry <= stop:
        return 0.0
    risk_amount = account_value * (risk_pct / 100)
    return round(risk_amount / (entry - stop), 6)


def red_flags() -> list[str]:
    return PACK["quick_decisions"]["red_flags"]
