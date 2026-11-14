"""Catalog of health indicators AURA tracks.

Every threshold here is a PROTOTYPE RULE drawn from published research and common clinical
reference ranges. They are NOT clinically validated flight-medicine limits.

Each indicator has two layers of rules:

1. Absolute limits (safety net). Crossing a ``critical`` limit is a predefined high-risk
   condition; crossing a ``warning`` limit deserves attention whatever the baseline says.
2. Personal-baseline rules. A *sustained* deviation from the astronaut's own pre-flight
   baseline (see ``alerts.py``) raises a warning even inside Earth-normal ranges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Hazard(str, Enum):
    """NASA Human Research Program: the five hazards of human spaceflight."""

    RADIATION = "space_radiation"
    ISOLATION = "isolation_confinement"
    DISTANCE = "distance_from_earth"
    GRAVITY = "gravity_fields"
    ENVIRONMENT = "hostile_closed_environment"


class BodySystem(str, Enum):
    """Regions of the interactive body figure in the front end."""

    BRAIN = "brain"  # behavioural health, sleep
    HEART = "heart"  # cardiovascular
    LUNGS = "lungs"  # respiratory / cabin atmosphere
    METABOLIC = "metabolic"  # glucose, nutrition
    IMMUNE = "immune"  # temperature / infection
    MUSCULOSKELETAL = "musculoskeletal"  # bone and muscle loss
    WHOLE_BODY = "whole_body"  # radiation


class Direction(str, Enum):
    """Which direction of change is adverse for an indicator."""

    LOW = "low"
    HIGH = "high"
    BOTH = "both"


@dataclass(frozen=True)
class Limits:
    """Absolute limits. ``None`` means no limit on that side."""

    warning_low: float | None = None
    warning_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None


@dataclass(frozen=True)
class Indicator:
    key: str
    name: str
    unit: str
    body_system: BodySystem
    hazards: tuple[Hazard, ...]
    adverse_direction: Direction
    limits: Limits
    # Minimum change from baseline (in the indicator's units) that counts as clinically
    # meaningful. Stops tiny but statistically "significant" shifts from firing alerts when
    # an astronaut's baseline is very stable.
    min_meaningful_change: float
    decimals: int
    why_it_matters: str
    how_to_measure: str
    actions: dict[str, list[str]] = field(default_factory=dict)
    references: tuple[str, ...] = ()
    # False for environmental exposures (e.g. radiation), where an Earth-based personal
    # baseline is meaningless; only absolute limits apply.
    use_baseline: bool = True

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "unit": self.unit,
            "body_system": self.body_system.value,
            "hazards": [h.value for h in self.hazards],
            "adverse_direction": self.adverse_direction.value,
            "limits": self.limits.__dict__,
            "min_meaningful_change": self.min_meaningful_change,
            "decimals": self.decimals,
            "why_it_matters": self.why_it_matters,
            "how_to_measure": self.how_to_measure,
            "actions": self.actions,
            "references": list(self.references),
            "use_baseline": self.use_baseline,
        }


HRP_RISKS = "NASA HRP, Human Research Roadmap risk catalog: https://humanresearchroadmap.nasa.gov/"
NASA_STD_3001 = "NASA-STD-3001 Vol. 1, Crew Health (2022)"

INDICATORS: dict[str, Indicator] = {
    ind.key: ind
    for ind in [
        Indicator(
            key="heart_rate",
            name="Resting heart rate",
            unit="bpm",
            body_system=BodySystem.HEART,
            hazards=(Hazard.GRAVITY, Hazard.ISOLATION),
            adverse_direction=Direction.BOTH,
            limits=Limits(warning_low=45, warning_high=100, critical_low=38, critical_high=130),
            min_meaningful_change=6,
            decimals=0,
            why_it_matters=(
                "In microgravity, fluids shift towards the head and the heart works less, "
                "which leads to cardiovascular deconditioning. A sustained rise in resting "
                "heart rate can signal stress, poor sleep, dehydration, infection or early "
                "cardiovascular problems."
            ),
            how_to_measure=(
                "Measure on waking, before coffee or exercise. Sit still for 2 minutes, then "
                "read the pulse from the wearable or count it for 60 seconds."
            ),
            actions={
                "warning": [
                    "Re-measure after 5 minutes of quiet rest.",
                    "Drink water. Fluid loss is common in the first weeks of flight.",
                    "Review your sleep and stress. Both raise resting heart rate.",
                ],
                "critical": [
                    "Stop any exercise or strenuous task now.",
                    "Take a manual pulse and blood pressure, and record any chest pain, "
                    "dizziness or palpitations.",
                    "Contact the flight surgeon immediately.",
                ],
            },
            references=(
                HRP_RISKS + " (Risk of Cardiovascular Adaptations)",
                "Hughson et al., 'Cardiovascular regulation during long-duration spaceflights "
                "to the ISS', J Appl Physiol 112:719-727 (2012)",
            ),
        ),
        Indicator(
            key="systolic_bp",
            name="Systolic blood pressure",
            unit="mmHg",
            body_system=BodySystem.HEART,
            hazards=(Hazard.GRAVITY, Hazard.ENVIRONMENT),
            adverse_direction=Direction.BOTH,
            limits=Limits(warning_low=90, warning_high=140, critical_low=80, critical_high=180),
            min_meaningful_change=10,
            decimals=0,
            why_it_matters=(
                "Blood pressure regulation changes in weightlessness. High readings raise "
                "cardiovascular risk. Low readings can cause dizziness, especially when "
                "returning to gravity (orthostatic intolerance)."
            ),
            how_to_measure=(
                "Seated and rested for 5 minutes, cuff on the upper arm at heart level. Take "
                "2 readings 1 minute apart and log the average."
            ),
            actions={
                "warning": [
                    "Re-measure after 5 minutes of rest, with the cuff at heart level.",
                    "Cut back on salty rations today and keep drinking water.",
                    "Use a relaxation or breathing exercise if you feel stressed.",
                ],
                "critical": [
                    "Rest now and re-measure in 5 minutes.",
                    "Report any headache, vision changes or chest pain.",
                    "Contact the flight surgeon immediately.",
                ],
            },
            references=(
                HRP_RISKS + " (Risk of Cardiovascular Adaptations)",
                "Whelton et al., 2017 ACC/AHA Blood Pressure Guideline",
            ),
        ),
        Indicator(
            key="diastolic_bp",
            name="Diastolic blood pressure",
            unit="mmHg",
            body_system=BodySystem.HEART,
            hazards=(Hazard.GRAVITY, Hazard.ENVIRONMENT),
            adverse_direction=Direction.BOTH,
            limits=Limits(warning_low=55, warning_high=90, critical_low=45, critical_high=120),
            min_meaningful_change=8,
            decimals=0,
            why_it_matters=(
                "The pressure between heartbeats. Sustained high readings add to "
                "cardiovascular risk on long missions."
            ),
            how_to_measure="Measured at the same time as systolic pressure.",
            actions={
                "warning": [
                    "Re-measure after 5 minutes of rest.",
                    "Watch your salt and caffeine intake today.",
                ],
                "critical": [
                    "Rest and re-measure in 5 minutes.",
                    "Contact the flight surgeon immediately.",
                ],
            },
            references=("Whelton et al., 2017 ACC/AHA Blood Pressure Guideline",),
        ),
        Indicator(
            key="spo2",
            name="Blood oxygen (SpO2)",
            unit="%",
            body_system=BodySystem.LUNGS,
            hazards=(Hazard.ENVIRONMENT,),
            adverse_direction=Direction.LOW,
            limits=Limits(warning_low=94, critical_low=90),
            min_meaningful_change=2,
            decimals=0,
            why_it_matters=(
                "Shows how well your blood carries oxygen. A drop can point to a problem "
                "with the cabin atmosphere (for example CO2 build-up or a leak) or with your "
                "lungs."
            ),
            how_to_measure="Pulse oximeter on a warm finger, held still for 30 seconds.",
            actions={
                "warning": [
                    "Re-measure on another finger and warm your hands first.",
                    "Check the cabin CO2 and O2 readings on the life-support display.",
                    "Tell your crewmates if you feel short of breath or have a headache.",
                ],
                "critical": [
                    "Check the cabin atmosphere alarms now.",
                    "Use supplemental oxygen if your crew procedure calls for it.",
                    "Contact the flight surgeon immediately.",
                ],
            },
            references=(
                NASA_STD_3001,
                "WHO, 'Pulse Oximetry Training Manual' (2011)",
            ),
        ),
        Indicator(
            key="glucose",
            name="Blood glucose (fasting)",
            unit="mg/dL",
            body_system=BodySystem.METABOLIC,
            hazards=(Hazard.GRAVITY, Hazard.ENVIRONMENT),
            adverse_direction=Direction.BOTH,
            limits=Limits(warning_low=70, warning_high=125, critical_low=54, critical_high=250),
            min_meaningful_change=12,
            decimals=0,
            why_it_matters=(
                "Physical inactivity and microgravity can reduce insulin sensitivity, and "
                "eating too little is common in flight. Both highs and lows affect energy, "
                "focus and long-term health."
            ),
            how_to_measure="Finger-stick glucometer, fasting, before breakfast.",
            actions={
                "warning": [
                    "If low: eat a fast-acting carbohydrate (15 g) and re-test in 15 minutes.",
                    "If high: re-test after 2 hours and check you are hitting your exercise "
                    "target.",
                    "Log your meals today so the ground team can review your nutrition.",
                ],
                "critical": [
                    "If low and you feel shaky or confused: take 15 to 20 g of glucose now "
                    "and alert a crewmate.",
                    "If very high: drink water, re-test, and check for ketones if you can.",
                    "Contact the flight surgeon immediately.",
                ],
            },
            references=(
                HRP_RISKS + " (Risk of Inadequate Nutrition)",
                "American Diabetes Association, Standards of Care in Diabetes (2024)",
                "Hughson et al., 'Increased postflight carotid artery stiffness and inflight "
                "insulin resistance', Am J Physiol 310 (2016)",
            ),
        ),
        Indicator(
            key="body_temp",
            name="Body temperature",
            unit="°C",
            body_system=BodySystem.IMMUNE,
            hazards=(Hazard.ENVIRONMENT, Hazard.RADIATION),
            adverse_direction=Direction.BOTH,
            limits=Limits(warning_low=35.5, warning_high=37.9, critical_low=35.0, critical_high=39.0),
            min_meaningful_change=0.5,
            decimals=1,
            why_it_matters=(
                "Spaceflight can weaken the immune system and reactivate dormant viruses. "
                "A rise above your personal baseline is an early sign of infection. Core "
                "temperature runs about 1 °C higher in long-duration flight, so personal "
                "baselines matter here."
            ),
            how_to_measure="Oral or ear thermometer at rest, not within 30 min of exercise.",
            actions={
                "warning": [
                    "Re-measure in 1 hour, resting.",
                    "Drink fluids and note any symptoms such as a sore throat, cough or rash.",
                    "Limit close contact with crewmates until it is re-checked.",
                ],
                "critical": [
                    "Rest and keep hydrated.",
                    "Follow the crew medical kit fever procedure.",
                    "Contact the flight surgeon immediately.",
                ],
            },
            references=(
                "Stahn et al., 'Increased core body temperature in astronauts during "
                "long-duration space missions', Scientific Reports 7:16180 (2017)",
                HRP_RISKS + " (Risk of Adverse Health Event Due to Altered Immune Response)",
            ),
        ),
        Indicator(
            key="sleep_hours",
            name="Sleep duration",
            unit="h",
            body_system=BodySystem.BRAIN,
            hazards=(Hazard.ISOLATION, Hazard.ENVIRONMENT),
            adverse_direction=Direction.LOW,
            limits=Limits(warning_low=5.5, critical_low=4.0),
            min_meaningful_change=0.75,
            decimals=1,
            why_it_matters=(
                "Without a normal day and night, with noise and with heavy workloads, "
                "astronauts often sleep about 6 hours. Chronic short sleep harms attention, "
                "mood, immunity and the ability to perform critical tasks safely."
            ),
            how_to_measure="Read from the wearable sleep tracker, or log hours on waking.",
            actions={
                "warning": [
                    "Keep a fixed sleep window and dim the lights an hour before it.",
                    "Avoid caffeine in the 6 hours before sleep.",
                    "Use earplugs and an eye mask, and check your sleep station is ventilated.",
                ],
                "critical": [
                    "Tell your commander. Fatigue makes critical tasks less safe.",
                    "Ask for a rest period before EVA or other high-risk work.",
                    "Talk to the flight surgeon about a sleep plan.",
                ],
            },
            references=(
                "Barger et al., 'Prevalence of sleep deficiency and use of hypnotic drugs in "
                "astronauts', Lancet Neurology 13:904-912 (2014)",
                HRP_RISKS + " (Risk of Performance Decrements Due to Sleep Loss)",
            ),
        ),
        Indicator(
            key="mood",
            name="Mood (self-report)",
            unit="/10",
            body_system=BodySystem.BRAIN,
            hazards=(Hazard.ISOLATION, Hazard.DISTANCE),
            adverse_direction=Direction.LOW,
            limits=Limits(warning_low=4, critical_low=2),
            min_meaningful_change=1.5,
            decimals=0,
            why_it_matters=(
                "Isolation, confinement and distance from Earth affect behavioural health. "
                "A gradual drop in mood is easy to miss on your own, but it shows up "
                "clearly in a trend."
            ),
            how_to_measure="Rate your overall mood today from 1 (very low) to 10 (excellent).",
            actions={
                "warning": [
                    "Schedule a private call with family or friends.",
                    "Take a 10-minute break: window viewing, music or a hobby.",
                    "Share how you feel with a crewmate you trust.",
                ],
                "critical": [
                    "Reach out now to the behavioural health team on the ground.",
                    "Let your commander know you need support.",
                ],
            },
            references=(
                HRP_RISKS + " (Risk of Adverse Cognitive or Behavioral Conditions)",
                "Basner et al., 'Mars 520-d mission simulation reveals protracted crew "
                "hypokinesis and alterations of sleep duration and timing', PNAS 110 (2013)",
            ),
        ),
        Indicator(
            key="exercise_minutes",
            name="Exercise countermeasures",
            unit="min",
            body_system=BodySystem.MUSCULOSKELETAL,
            hazards=(Hazard.GRAVITY,),
            adverse_direction=Direction.LOW,
            limits=Limits(warning_low=75, critical_low=30),
            min_meaningful_change=20,
            decimals=0,
            why_it_matters=(
                "Without gravity, bones can lose about 1 to 1.5% of their mass per month "
                "and muscles weaken. About 2 hours of daily resistance and aerobic exercise "
                "is the main protection."
            ),
            how_to_measure="Minutes logged on the treadmill, cycle and resistance device today.",
            actions={
                "warning": [
                    "Plan a catch-up resistance session tomorrow.",
                    "Prioritise loading exercises such as squats and deadlifts for bone health.",
                ],
                "critical": [
                    "Tell the ground team so the schedule can make room for exercise.",
                    "Check for injury or pain that is stopping you from exercising.",
                ],
            },
            references=(
                "Sibonga et al., 'Evidence Report: Risk of Bone Fracture due to Spaceflight-"
                "induced Changes to Bone', NASA HRP (2017)",
                "Loehr et al., 'Physical training for long-duration spaceflight', Aerosp Med "
                "Hum Perform 86 (2015)",
            ),
        ),
        Indicator(
            key="radiation_dose",
            name="Radiation dose (daily)",
            unit="mSv",
            body_system=BodySystem.WHOLE_BODY,
            hazards=(Hazard.RADIATION, Hazard.DISTANCE),
            adverse_direction=Direction.HIGH,
            limits=Limits(warning_high=2.0, critical_high=10.0),
            min_meaningful_change=0.3,
            decimals=2,
            why_it_matters=(
                "Outside Earth's magnetic field, crews are exposed to galactic cosmic rays "
                "and solar particle events. These raise long-term cancer risk and can harm "
                "the central nervous system. NASA's career limit is 600 mSv."
            ),
            how_to_measure="Read from your personal dosimeter at the end of each day.",
            actions={
                "warning": [
                    "Check the space-weather feed for a solar particle event.",
                    "Cut time in less-shielded modules for the rest of the day.",
                ],
                "critical": [
                    "Go to the storm shelter or most-shielded area now.",
                    "Contact mission control and the flight surgeon.",
                ],
            },
            references=(
                NASA_STD_3001 + " (600 mSv career effective dose limit)",
                "Zeitlin et al., 'Measurements of energetic particle radiation in transit to "
                "Mars on the Mars Science Laboratory', Science 340:1080 (2013)",
                "CSA, 'Monitoring radiation for astronaut health'",
            ),
            use_baseline=False,
        ),
    ]
}


def get_indicator(key: str) -> Indicator:
    try:
        return INDICATORS[key]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown indicator '{key}'") from exc
