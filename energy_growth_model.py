"""
Toy simulation: given daily exogenous income, compare strategies for allocating
cash between an interest-bearing instrument and direct energy purchases
(Refill + Xanax), tracking cumulative energy (E) bought over time.

This is a pure "maximize cumulative E" model — it does NOT model the stat
compounding (dStat/dEnergy ~ Stat) discussed earlier. E itself is treated as a
plain additive resource here.

Both purchase channels are HARD-CAPPED per day:
  - Refill: 1/day (real game mechanic).
  - Xanax: 2.5/day on average (a per-playstyle cooldown limit) — modeled as an
    alternating 3-then-2 pattern across consecutive days, since a real ~9.6h
    cooldown lands you on one or the other depending on phase, not a literal
    fractional dose. This puts a hard ceiling on energy purchased per day, no
    matter how much cash is available that day.

The instrument pays out once every CYCLE_DAYS, as a lump sum, not smoothed —
so any strategy that wants to actually SUSTAIN hitting the daily cap between
payouts has to hold back a cash reserve sized to cover the gap, rather than
reinvesting every lump the moment it arrives.

All dollar figures are placeholders — tune the ASSUMPTIONS block to taste.
"""

# ---- ASSUMPTIONS (tune these) ----------------------------------------------
DAILY_INCOME = 250_000          # exogenous cash/day from plushie/flower running (guess — replace)
XANAX_PRICE = 850_000           # per the earlier hypothetical (fixed, no side effects)
XANAX_ENERGY = 250
POINT_PRICE = 31_198            # live points-market price pulled during this session
REFILL_POINTS = 30
REFILL_ENERGY = 150             # your max energy — adjust to your actual value
REFILL_COST = POINT_PRICE * REFILL_POINTS
REFILL_PER_DAY = 1

CYCLE_DAYS = 14                 # instrument payout cycle
ANNUAL_RATE = 0.18               # 18%/yr, the actual assumption
CYCLE_RATE = (1 + ANNUAL_RATE) ** (CYCLE_DAYS / 365) - 1  # -> ~0.637% per 14-day cycle

HORIZON_DAYS = 730              # 2 years
CHECKPOINT_EVERY = 60


def xanax_cap_for_day(day):
    """Alternating 3/2 pattern averaging 2.5/day over any 2-day window."""
    return 3 if day % 2 == 0 else 2


def daily_cap_cost(day):
    return REFILL_COST * REFILL_PER_DAY + XANAX_PRICE * xanax_cap_for_day(day)


def daily_cap_energy(day):
    return REFILL_ENERGY * REFILL_PER_DAY + XANAX_ENERGY * xanax_cap_for_day(day)


def cost_of_days(start_day, n):
    return sum(daily_cap_cost(d) for d in range(start_day, start_day + n))


def days_until_next_payout(day):
    """Days from `day` (inclusive) through the next payout day (inclusive)."""
    if day % CYCLE_DAYS == 0:
        return CYCLE_DAYS
    return CYCLE_DAYS - (day % CYCLE_DAYS)


def buy_energy(cash, day):
    """Spend cash via merit order (cheapest $/energy first), bounded by the
    day's hard caps on both channels. Returns (energy_bought, cash_left)."""
    energy = 0
    refills_left = REFILL_PER_DAY
    xanax_left = xanax_cap_for_day(day)
    refill_per_energy = REFILL_COST / REFILL_ENERGY
    xanax_per_energy = XANAX_PRICE / XANAX_ENERGY
    cheap_is_refill = refill_per_energy <= xanax_per_energy

    def try_refill():
        nonlocal cash, energy, refills_left
        while refills_left > 0 and cash >= REFILL_COST:
            cash -= REFILL_COST
            energy += REFILL_ENERGY
            refills_left -= 1

    def try_xanax():
        nonlocal cash, energy, xanax_left
        while xanax_left > 0 and cash >= XANAX_PRICE:
            cash -= XANAX_PRICE
            energy += XANAX_ENERGY
            xanax_left -= 1

    if cheap_is_refill:
        try_refill()
        try_xanax()
    else:
        try_xanax()
        try_refill()

    return energy, cash


def simulate(strategy, horizon_days=HORIZON_DAYS):
    """strategy(day, principal, available) -> dollars to invest today (the
    rest is kept as spendable cash: today's purchase, plus whatever's held
    as reserve for future days, carried forward uninvested)."""
    principal = 0.0
    carryover_cash = 0.0
    cumulative_energy = 0
    trajectory = []

    for day in range(1, horizon_days + 1):
        payout_today = principal * CYCLE_RATE if day % CYCLE_DAYS == 0 else 0.0
        available = carryover_cash + DAILY_INCOME + payout_today

        invest_amount = strategy(day, principal, available)
        invest_amount = max(0.0, min(available, invest_amount))
        working_cash = available - invest_amount

        energy_today, leftover = buy_energy(working_cash, day)
        cumulative_energy += energy_today

        principal += invest_amount
        carryover_cash = leftover  # kept as reserve for future days, NOT invested

        if day % CHECKPOINT_EVERY == 0 or day == horizon_days:
            trajectory.append((day, cumulative_energy, principal, carryover_cash))

    return trajectory


def strategy_cap_then_invest(day, principal, available):
    """Reserve enough cash to fully fund every day up to (and including) the
    next payout, spend today's slice of that immediately (handled by
    buy_energy's own daily cap), and invest only genuine surplus beyond that
    reserve. This is the mechanical optimum once hard daily caps exist."""
    reserve_needed = cost_of_days(day, days_until_next_payout(day))
    return max(0.0, available - reserve_needed)


def strategy_bank_then_harvest(day, principal, available):
    """Invest everything until the instrument's own payout alone covers a
    full cycle of daily caps, then switch to cap-then-invest."""
    cycle_payout_now = principal * CYCLE_RATE
    target = cost_of_days(1, CYCLE_DAYS)
    if cycle_payout_now >= target:
        return strategy_cap_then_invest(day, principal, available)
    return available  # hold everything back (invest all of it)


def print_trajectory(name, trajectory):
    print(f"\n=== {name} ===")
    print(f"{'day':>5} {'cum. energy':>14} {'principal':>18} {'reserve cash':>14}")
    for day, energy, principal, reserve in trajectory:
        print(f"{day:>5} {energy:>14,} {'$' + format(int(principal), ','):>18} {'$' + format(int(reserve), ','):>14}")


if __name__ == "__main__":
    avg_cap_energy = (daily_cap_energy(1) + daily_cap_energy(2)) / 2
    avg_cap_cost = (daily_cap_cost(1) + daily_cap_cost(2)) / 2
    print(f"Refill: ${REFILL_COST:,.0f} -> {REFILL_ENERGY}E  (${REFILL_COST/REFILL_ENERGY:,.0f}/E), {REFILL_PER_DAY}/day")
    print(f"Xanax:  ${XANAX_PRICE:,.0f} -> {XANAX_ENERGY}E  (${XANAX_PRICE/XANAX_ENERGY:,.0f}/E), 2.5/day avg")
    print(f"Hard daily cap: {avg_cap_energy:.0f}E/day avg, costing ${avg_cap_cost:,.0f}/day avg to fully hit")
    print(f"Daily income assumption: ${DAILY_INCOME:,.0f} ({'BELOW' if DAILY_INCOME < avg_cap_cost else 'ABOVE'} the cap cost on its own)")
    print(f"Theoretical max cumulative energy at day {HORIZON_DAYS} if cap-bound from day 1: {avg_cap_energy*HORIZON_DAYS:,.0f}")

    results = {
        "cap-then-invest (optimal)": simulate(strategy_cap_then_invest),
        "bank-then-harvest": simulate(strategy_bank_then_harvest),
    }

    for name, traj in results.items():
        print_trajectory(name, traj)

    print("\n=== Cumulative energy at each horizon, both strategies ===")
    checkpoints = [t[0] for t in next(iter(results.values()))]
    header = "day".rjust(6) + "".join(name.rjust(28) for name in results)
    print(header)
    for i, day in enumerate(checkpoints):
        row = str(day).rjust(6)
        for name, traj in results.items():
            row += f"{traj[i][1]:,}".rjust(28)
        print(row)
