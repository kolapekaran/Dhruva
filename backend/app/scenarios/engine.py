"""
engine.py

The core Scenario Engine.

Design idea (composability):
------------------------------
Instead of writing one big block of if/elif statements for every possible
combination of conditions, we define a small list of independent "rules".

Each rule knows only two things:
1. How to check if IT'S condition is true, given a ScenarioInput.
2. What risk score and recommendation to contribute if it IS true.

The engine then loops over all rules once, collects whichever ones matched,
and combines their risk scores and recommendations. This means:

- Adding a brand new condition later = adding ONE new rule to the list.
- No combination of conditions needs its own special-case code.
- COMBINED_EXTREME is just an extra check on "how many rules matched",
  not a hardcoded combination of specific scenarios.
"""

from dataclasses import dataclass
from typing import Callable

from .models import ScenarioInput, ScenarioResult, ScenarioType

# A "check" is just a function that takes a ScenarioInput and returns
# True/False depending on whether that specific condition is present.
ConditionCheck = Callable[[ScenarioInput], bool]


@dataclass(frozen=True)
class ScenarioRule:
    """
    A single, independent rule.

    Each rule is fully self-contained: given a ScenarioInput, it can decide
    on its own whether it applies, and if so, how much risk it adds and
    what recommendation to give. The engine does not need to know anything
    about the *meaning* of a rule to use it.
    """

    scenario_type: ScenarioType
    check: ConditionCheck
    risk_weight: float
    recommendation: str


# ---------------------------------------------------------------------------
# The list of independent rules.
#
# This is the ONLY place you need to touch to add a new condition in the
# future. You do not need to touch ScenarioEngine.evaluate() at all.
# ---------------------------------------------------------------------------
SCENARIO_RULES: list[ScenarioRule] = [
    ScenarioRule(
        scenario_type=ScenarioType.EXTREME_COLD,
        check=lambda data: data.temperature <= -30,
        risk_weight=20,
        recommendation="Increase heating priority and monitor power consumption.",
    ),
    ScenarioRule(
        scenario_type=ScenarioType.LOW_WIND,
        check=lambda data: data.wind_percent < 60,
        risk_weight=10,
        recommendation="Reduce dependence on wind generation.",
    ),
    ScenarioRule(
        scenario_type=ScenarioType.NO_SOLAR,
        check=lambda data: data.solar_available is False,
        risk_weight=15,
        recommendation="Use battery and backup generation because solar is unavailable.",
    ),
    ScenarioRule(
        scenario_type=ScenarioType.HIGH_LOAD,
        check=lambda data: data.load_percent > 120,
        risk_weight=15,
        recommendation="Reduce non-critical electrical loads.",
    ),
    ScenarioRule(
        scenario_type=ScenarioType.BATTERY_DEGRADED,
        check=lambda data: data.battery_health < 50,
        risk_weight=20,
        recommendation="Avoid deep battery discharge and prioritize critical loads.",
    ),
    ScenarioRule(
        scenario_type=ScenarioType.DIESEL_FAILURE,
        check=lambda data: data.diesel_available is False,
        risk_weight=25,
        recommendation="Diesel backup is unavailable. Preserve stored energy.",
    ),
    ScenarioRule(
        scenario_type=ScenarioType.FUEL_SHORTAGE,
        check=lambda data: data.fuel_percent < 25,
        risk_weight=20,
        recommendation="Conserve fuel and prioritize critical generator operation.",
    ),
    ScenarioRule(
        scenario_type=ScenarioType.RESUPPLY_DELAY,
        check=lambda data: data.resupply_delay_days >= 7,
        risk_weight=15,
        recommendation="Conserve fuel and energy until resupply arrives.",
    ),
]

# Extra risk added on top when 3+ independent scenarios are detected.
COMBINED_EXTREME_THRESHOLD = 3
COMBINED_EXTREME_RISK_WEIGHT = 10
COMBINED_EXTREME_RECOMMENDATION = "Activate emergency energy management strategy."

MAX_RISK = 100.0

# Severity thresholds: (max risk value INCLUSIVE for this band, label)
# Checked in order, so the first band whose max the risk falls under wins.
SEVERITY_BANDS: list[tuple[float, str]] = [
    (19, "LOW"),
    (39, "MEDIUM"),
    (69, "HIGH"),
    (100, "CRITICAL"),
]


class ScenarioEngine:
    """
    Evaluates a ScenarioInput against all known rules and produces a
    ScenarioResult.

    This class contains NO knowledge of specific combinations. It simply:
    1. Runs every rule independently.
    2. Collects whichever ones matched.
    3. Adds a COMBINED_EXTREME bonus if enough rules matched.
    4. Sums risk, caps it at 100, and maps it to a severity label.
    """

    def __init__(self, rules: list[ScenarioRule] | None = None) -> None:
        # Rules are injected so they can be swapped/extended/tested
        # independently of the engine itself if needed later.
        self.rules = rules if rules is not None else SCENARIO_RULES

    def evaluate(self, data: ScenarioInput) -> ScenarioResult:
        """
        Run every rule against `data` and build a combined ScenarioResult.
        """
        detected_scenarios: list[ScenarioType] = []
        recommendations: list[str] = []
        total_risk = 0.0

        # Step 1: check every rule independently. No rule knows about
        # any other rule, so any combination "just works".
        for rule in self.rules:
            if rule.check(data):
                detected_scenarios.append(rule.scenario_type)
                recommendations.append(rule.recommendation)
                total_risk += rule.risk_weight

        # Step 2: if nothing was detected, the station is operating normally.
        if not detected_scenarios:
            return ScenarioResult(
                scenarios=[ScenarioType.NORMAL.value],
                severity="LOW",
                recommendations=[],
                estimated_risk=0.0,
            )

        # Step 3: dynamically add COMBINED_EXTREME based on how many
        # independent scenarios were found — not on which specific ones.
        if len(detected_scenarios) >= COMBINED_EXTREME_THRESHOLD:
            detected_scenarios.append(ScenarioType.COMBINED_EXTREME)
            recommendations.append(COMBINED_EXTREME_RECOMMENDATION)
            total_risk += COMBINED_EXTREME_RISK_WEIGHT

        # Step 4: cap risk and determine severity.
        total_risk = min(total_risk, MAX_RISK)
        severity = self._risk_to_severity(total_risk)

        return ScenarioResult(
            scenarios=[s.value for s in detected_scenarios],
            severity=severity,
            recommendations=recommendations,
            estimated_risk=total_risk,
        )

    @staticmethod
    def _risk_to_severity(risk: float) -> str:
        """Map a numeric risk score to a severity label."""
        for max_value, label in SEVERITY_BANDS:
            if risk <= max_value:
                return label
        return "CRITICAL"  # Fallback safety net; should not normally be hit.