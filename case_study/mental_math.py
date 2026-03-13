"""
Mental math drill engine for case interview preparation.

Generates timed arithmetic problems across five categories that
interviewers commonly test: percentages, growth rates (CAGR),
market sizing multiplications, breakeven analysis, and unit economics.
"""

from __future__ import annotations

import math
import random
import time as _time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Drill categories
# ---------------------------------------------------------------------------

DRILL_CATEGORIES = {
    "percentage": "Percentages",
    "growth": "Growth & CAGR",
    "market_sizing": "Market Sizing Math",
    "breakeven": "Breakeven Analysis",
    "unit_economics": "Unit Economics",
}

CATEGORY_DESCRIPTIONS = {
    "percentage": "Quickly compute percentages of large numbers — a bread-and-butter case skill.",
    "growth": "Estimate compound annual growth rates and future values.",
    "market_sizing": "Multiply and divide large numbers fast for TAM estimates.",
    "breakeven": "Find breakeven volumes, margins, and payback periods.",
    "unit_economics": "Compute LTV, CAC payback, contribution margin, and similar metrics.",
}

# Target time per problem (seconds)
TARGET_TIME = 30


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Drill:
    """A single mental math problem."""
    category: str
    question: str
    answer: float
    unit: str = ""
    tolerance: float = 0.05  # fraction — 5% default
    hint: str = ""

    def check(self, user_answer: float) -> bool:
        """Return True if user_answer is within tolerance of the correct answer."""
        if self.answer == 0:
            return abs(user_answer) < 1e-6
        return abs(user_answer - self.answer) / abs(self.answer) <= self.tolerance


@dataclass
class DrillResult:
    """Result of a single attempted drill."""
    drill: Drill
    user_answer: float | None
    correct: bool
    time_seconds: float


@dataclass
class DrillSession:
    """A complete drill session (set of problems)."""
    category: str
    difficulty: str
    results: list[DrillResult] = field(default_factory=list)
    started_at: float = 0.0

    @property
    def total_correct(self) -> int:
        return sum(1 for r in self.results if r.correct)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def accuracy(self) -> float:
        return self.total_correct / self.total_count if self.total_count else 0

    @property
    def avg_time(self) -> float:
        times = [r.time_seconds for r in self.results]
        return sum(times) / len(times) if times else 0

    @property
    def score(self) -> int:
        """0-100 score based on accuracy (70%) and speed (30%)."""
        if not self.results:
            return 0
        accuracy_score = self.accuracy * 70
        # Speed: full marks if avg <= TARGET_TIME, linearly down to 0 at 3x target
        speed_ratio = min(self.avg_time / TARGET_TIME, 3.0)
        speed_score = max(0, (1 - (speed_ratio - 1) / 2)) * 30 if speed_ratio > 1 else 30
        return round(accuracy_score + speed_score)


# ---------------------------------------------------------------------------
# Problem generators
# ---------------------------------------------------------------------------

def _pick_large_number(difficulty: str) -> tuple[float, str]:
    """Return a (value, formatted_string) for a large number."""
    if difficulty == "beginner":
        choices = [
            (100_000, "100K"), (200_000, "200K"), (500_000, "500K"),
            (1_000_000, "1 million"), (2_000_000, "2 million"),
            (5_000_000, "5 million"), (10_000_000, "10 million"),
        ]
    elif difficulty == "intermediate":
        choices = [
            (3_000_000, "3 million"), (7_500_000, "7.5 million"),
            (12_000_000, "12 million"), (25_000_000, "25 million"),
            (80_000_000, "80 million"), (150_000_000, "150 million"),
            (240_000_000, "240 million"), (330_000_000, "330 million"),
        ]
    else:
        choices = [
            (17_000_000, "17 million"), (43_000_000, "43 million"),
            (85_000_000, "85 million"), (127_000_000, "127 million"),
            (240_000_000, "240 million"), (375_000_000, "375 million"),
            (1_200_000_000, "1.2 billion"), (2_700_000_000, "2.7 billion"),
        ]
    return random.choice(choices)


def _generate_percentage(difficulty: str) -> Drill:
    """Generate a percentage-of-large-number problem."""
    value, value_str = _pick_large_number(difficulty)

    if difficulty == "beginner":
        pcts = [10, 20, 25, 50, 5, 1]
    elif difficulty == "intermediate":
        pcts = [12, 15, 8, 30, 35, 7, 3, 18]
    else:
        pcts = [12, 17, 23, 8.5, 6.5, 14, 37, 42, 2.5]

    pct = random.choice(pcts)
    answer = value * pct / 100
    pct_str = f"{pct:g}%"

    return Drill(
        category="percentage",
        question=f"What is {pct_str} of {value_str}?",
        answer=answer,
        tolerance=0.05,
        hint=f"Try: {pct_str} = break into simpler pieces (e.g. 10% + 2%)",
    )


def _generate_growth(difficulty: str) -> Drill:
    """Generate a CAGR or future-value problem."""
    problem_type = random.choice(["cagr", "future_value"])

    if problem_type == "cagr":
        if difficulty == "beginner":
            starts = [100, 200, 1000]
            ends_mult = [1.5, 2.0, 1.2]
            years_list = [3, 5, 2]
        elif difficulty == "intermediate":
            starts = [100, 250, 500, 80]
            ends_mult = [1.5, 1.8, 2.5, 1.3]
            years_list = [3, 4, 5, 2]
        else:
            starts = [100, 150, 300, 75]
            ends_mult = [1.44, 1.72, 2.1, 3.0]
            years_list = [3, 4, 5, 7]

        idx = random.randrange(len(starts))
        start = starts[idx]
        mult = ends_mult[idx]
        years = years_list[idx]
        end = start * mult
        cagr = (mult ** (1 / years) - 1) * 100

        return Drill(
            category="growth",
            question=f"What CAGR takes {start} to {end:g} in {years} years?",
            answer=round(cagr, 1),
            unit="%",
            tolerance=0.15,  # CAGR estimation is harder — allow 15%
            hint=f"Rule of 72: doubling time ~ 72/rate. Try working backwards.",
        )
    else:
        # Future value
        if difficulty == "beginner":
            base = random.choice([100, 1000, 500])
            rate = random.choice([10, 20, 5])
            years = random.choice([2, 3])
        elif difficulty == "intermediate":
            base = random.choice([200, 500, 1000, 250])
            rate = random.choice([8, 12, 15, 25])
            years = random.choice([3, 4, 5])
        else:
            base = random.choice([150, 300, 800])
            rate = random.choice([7, 11, 18, 22])
            years = random.choice([3, 5, 4])

        answer = base * (1 + rate / 100) ** years

        return Drill(
            category="growth",
            question=f"If {base} grows at {rate}% per year for {years} years, what is the final value?",
            answer=round(answer, 0),
            tolerance=0.10,
            hint=f"Compound: multiply by {1 + rate/100} each year, or estimate (1+r)^n.",
        )


def _generate_market_sizing(difficulty: str) -> Drill:
    """Generate a large-number multiplication/division for market sizing."""
    if difficulty == "beginner":
        problems = [
            ("330 million people x $50 average spend", 330_000_000 * 50),
            ("120 million households x $200/month", 120_000_000 * 200),
            ("50 million users x $10/year", 50_000_000 * 10),
            ("1 billion people x 2 meals/day x 365 days", 1_000_000_000 * 2 * 365),
        ]
    elif difficulty == "intermediate":
        problems = [
            ("330M people x 70% adults x $120 avg spend", 330_000_000 * 0.70 * 120),
            ("25M small businesses x 40% adoption x $500/yr", 25_000_000 * 0.40 * 500),
            ("$45B market / 150M users — what is revenue per user?", 45_000_000_000 / 150_000_000),
            ("80M households x 30% penetration x $75/month x 12", 80_000_000 * 0.30 * 75 * 12),
        ]
    else:
        problems = [
            ("145M workers x 22% remote x $2,400/yr on home office", 145_000_000 * 0.22 * 2400),
            ("$18B revenue / 45K employees — revenue per employee?", 18_000_000_000 / 45_000),
            ("330M pop x 78% adult x 45% smartphone x $35 app spend", 330_000_000 * 0.78 * 0.45 * 35),
            ("4.5M new cars/yr x $35K avg price x 3% margin", 4_500_000 * 35_000 * 0.03),
        ]

    question, answer = random.choice(problems)
    return Drill(
        category="market_sizing",
        question=question,
        answer=answer,
        tolerance=0.10,
        hint="Break into pieces: round aggressively, multiply step by step.",
    )


def _generate_breakeven(difficulty: str) -> Drill:
    """Generate a breakeven volume or payback problem."""
    if difficulty == "beginner":
        fixed = random.choice([100_000, 500_000, 1_000_000])
        margin = random.choice([10, 25, 50, 100])
    elif difficulty == "intermediate":
        fixed = random.choice([2_000_000, 5_000_000, 750_000])
        margin = random.choice([15, 35, 80, 120])
    else:
        fixed = random.choice([3_500_000, 8_000_000, 12_000_000])
        margin = random.choice([22, 45, 65, 150])

    problem_type = random.choice(["volume", "margin"])

    if problem_type == "volume":
        answer = fixed / margin
        fixed_str = f"${fixed:,.0f}" if fixed < 1_000_000 else f"${fixed/1_000_000:g}M"
        return Drill(
            category="breakeven",
            question=f"Fixed costs: {fixed_str}. Contribution margin: ${margin}/unit. Breakeven volume?",
            answer=answer,
            unit="units",
            tolerance=0.05,
            hint="Breakeven = Fixed Costs / Contribution Margin per unit.",
        )
    else:
        # Given volume, find required margin
        volume = random.choice([10_000, 50_000, 100_000, 200_000])
        answer = fixed / volume
        fixed_str = f"${fixed:,.0f}" if fixed < 1_000_000 else f"${fixed/1_000_000:g}M"
        return Drill(
            category="breakeven",
            question=f"Fixed costs: {fixed_str}. Expected volume: {volume:,} units. Required margin per unit to break even?",
            answer=answer,
            unit="$/unit",
            tolerance=0.05,
            hint="Required margin = Fixed Costs / Volume.",
        )


def _generate_unit_economics(difficulty: str) -> Drill:
    """Generate a unit economics problem (LTV, CAC payback, etc.)."""
    problem_type = random.choice(["ltv", "cac_payback", "contribution_margin"])

    if problem_type == "ltv":
        if difficulty == "beginner":
            arpu = random.choice([10, 20, 50])
            churn = random.choice([5, 10, 20])
        elif difficulty == "intermediate":
            arpu = random.choice([25, 45, 80, 120])
            churn = random.choice([3, 8, 12, 15])
        else:
            arpu = random.choice([35, 67, 95, 150])
            churn = random.choice([2.5, 4, 7, 11])

        # LTV = ARPU / churn rate (monthly)
        ltv = arpu / (churn / 100)
        return Drill(
            category="unit_economics",
            question=f"Monthly ARPU: ${arpu}. Monthly churn: {churn:g}%. What is the LTV?",
            answer=ltv,
            unit="$",
            tolerance=0.05,
            hint="LTV = ARPU / Churn Rate (as decimal).",
        )
    elif problem_type == "cac_payback":
        cac = random.choice([200, 500, 1000, 1500, 300])
        monthly_margin = random.choice([25, 50, 75, 100, 150])
        answer = cac / monthly_margin
        return Drill(
            category="unit_economics",
            question=f"CAC: ${cac}. Monthly contribution margin: ${monthly_margin}. Payback period in months?",
            answer=answer,
            unit="months",
            tolerance=0.05,
            hint="Payback = CAC / Monthly Contribution Margin.",
        )
    else:
        # Contribution margin calculation
        price = random.choice([50, 100, 200, 75, 150])
        if difficulty == "beginner":
            cogs_pct = random.choice([20, 40, 50])
        else:
            cogs_pct = random.choice([25, 35, 42, 55, 68])
        cogs = price * cogs_pct / 100
        variable_other = random.choice([5, 10, 15, 0])
        margin = price - cogs - variable_other
        margin_pct = margin / price * 100

        q = f"Price: ${price}. COGS: {cogs_pct}% of price."
        if variable_other > 0:
            q += f" Other variable costs: ${variable_other}/unit."
        q += " Contribution margin %?"

        return Drill(
            category="unit_economics",
            question=q,
            answer=round(margin_pct, 1),
            unit="%",
            tolerance=0.08,
            hint="Margin = (Price - COGS - Variable) / Price x 100.",
        )


# ---------------------------------------------------------------------------
# Generator dispatch
# ---------------------------------------------------------------------------

_GENERATORS = {
    "percentage": _generate_percentage,
    "growth": _generate_growth,
    "market_sizing": _generate_market_sizing,
    "breakeven": _generate_breakeven,
    "unit_economics": _generate_unit_economics,
}


def generate_drill(category: str, difficulty: str = "intermediate") -> Drill:
    """Generate a single drill problem for the given category and difficulty."""
    gen = _GENERATORS.get(category)
    if gen is None:
        raise ValueError(f"Unknown category: {category}")
    return gen(difficulty)


def generate_drill_set(
    category: str,
    count: int = 10,
    difficulty: str = "intermediate",
) -> list[Drill]:
    """Generate a set of drill problems."""
    return [generate_drill(category, difficulty) for _ in range(count)]


def generate_mixed_set(
    count: int = 10,
    difficulty: str = "intermediate",
) -> list[Drill]:
    """Generate a mixed set pulling from all categories."""
    categories = list(_GENERATORS.keys())
    drills = []
    for _ in range(count):
        cat = random.choice(categories)
        drills.append(generate_drill(cat, difficulty))
    return drills


def format_answer(value: float) -> str:
    """Format a numeric answer for display."""
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"${value/1_000_000_000:,.1f}B"
    if abs_val >= 1_000_000:
        return f"{value/1_000_000:,.1f}M"
    if abs_val >= 1_000:
        return f"{value:,.0f}"
    if value == int(value):
        return f"{int(value)}"
    return f"{value:,.1f}"
