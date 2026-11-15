"""Crew-to-ground messaging with a realistic signal delay.

Far from Earth, the flight surgeon can't answer straight away. A message to ground from a Mars
transit vehicle takes minutes to arrive, and the reply takes as long to come back. AURA has to
work on its own in that gap, and this module makes the gap visible.

Delay model (one-way light time, plus a little relay overhead):
* ISS: about 0.5 s through the TDRS relay satellites. Contact is effectively live.
* Lunar surface: about 1.3 s (mean Earth-Moon distance, 384,400 km).
* Mars transit: grows as the vehicle leaves Earth. The demo compresses the transit into the
  mission length, from about 0.2 min at day 1 to about 12.5 min at the end (1.5 AU). The real
  Earth-Mars delay ranges from about 3 to 22 minutes.

By default the ground's reply is SIMULATED: a rule-based message built from the crew member's
AURA status, labelled as such. In LIVE ground mode a person at the Flight surgeon console reads
each message once its signal reaches Earth and types the reply, which then travels back with the
same delay. There is still no real spacecraft link. A demo clock (DEMO_SPEED) shortens the wait
so a 12 minute delay takes 12 seconds on screen; the true delay is always shown.
"""

from __future__ import annotations

import itertools
import threading
from datetime import datetime, timedelta, timezone

LIGHT_MIN_PER_AU = 8.317
MARS_START_AU = 0.02
MARS_END_AU = 1.5
DEMO_SPEED = 60  # 1 real second on screen = 1 minute of signal travel
GROUND_HANDLING_S = 300  # the flight surgeon takes ~5 minutes to read and answer

SOURCES = {
    "iss": "NASA SCaN: ISS communications relay through TDRS (sub-second delay)",
    "lunar_surface": "Mean Earth-Moon distance 384,400 km / speed of light = 1.28 s",
    "mars_transit": "NASA: Earth-Mars one-way light time ranges from about 3 to 22 minutes",
}


def one_way_seconds(environment: str, day: int, mission_days: int) -> float:
    """True one-way signal delay to Earth for this environment on this mission day."""
    if environment == "iss":
        return 0.5
    if environment == "lunar_surface":
        return 1.3
    if environment == "mars_transit":
        progress = min(max(day, 1), mission_days) / max(mission_days, 1)
        au = MARS_START_AU + (MARS_END_AU - MARS_START_AU) * progress
        return round(au * LIGHT_MIN_PER_AU * 60, 1)
    return 0.0


def describe(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} s"
    return f"{seconds / 60:.1f} min"


def link_status(environment: str, day: int, mission_days: int) -> dict:
    s = one_way_seconds(environment, day, mission_days)
    autonomous = s >= 60
    return {
        "environment": environment,
        "day": day,
        "one_way_s": s,
        "round_trip_s": round(2 * s, 1),
        "one_way": describe(s),
        "round_trip": describe(2 * s),
        "ground_reply_s": round(2 * s + GROUND_HANDLING_S, 1),
        "demo_speed": DEMO_SPEED,
        "mode": "autonomous" if autonomous else "live",
        "explanation": (
            f"A message takes {describe(s)} to reach Earth and a reply at least {describe(2 * s)} "
            "round trip. AURA's guidance is your first line of support until ground answers."
            if autonomous
            else f"Ground contact is near real time ({describe(s)} each way)."
        ),
        "source": SOURCES.get(environment, ""),
    }


# ---------------------------------------------------------------- simulated ground reply
def ground_reply(status: dict | None, name: str, text: str, priority: str, day: int) -> str:
    """A rule-based flight surgeon reply built from the crew member's status when they wrote."""
    first = name.split()[-1]
    inds = status["indicators"] if status else []
    crit = [i for i in inds if i["level"] == "critical"]
    warn = [i for i in inds if i["level"] == "warning"]
    quote = text.strip().replace("\n", " ")
    quote = quote if len(quote) <= 90 else quote[:87] + "..."
    lines = [f'Ground copies your day {day} message, {first}: "{quote}"']
    if status is None:
        lines.append("No status packet was attached, so we'll review your telemetry at the next downlink. "
                     "Keep following AURA's guidance in the meantime.")
    elif crit:
        names = ", ".join(i["name"].lower() for i in crit)
        lines.append(f"We see critical readings for {names}. Keep following AURA's critical actions now. "
                     "The flight surgeon is on console and reviewing your data; we'll stay on the loop.")
    elif warn:
        names = ", ".join(i["name"].lower() for i in warn[:3])
        lines.append(f"We see warnings for {names}. We agree with AURA's plan: follow the actions, "
                     "re-measure tomorrow and tell us if anything gets worse.")
    else:
        lines.append("Your indicators look nominal from here. Keep up the routine.")
    if priority == "urgent" and not crit:
        lines.append("You flagged this as urgent: if you feel worse, start the emergency checklist "
                     "and don't wait for us.")
    lines.append("Flight surgeon, Mission Control")
    return "\n".join(lines)


# ---------------------------------------------------------------- message store
class Outbox:
    """Messages between crew and ground, with arrival times on the demo clock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self.messages: list[dict] = []
        self.mode = "simulated"  # or "live": a person answers from the Flight surgeon console

    def clear(self) -> None:
        with self._lock:
            self.messages = []

    def send(self, crew_id: str, name: str, text: str, priority: str, day: int, link: dict,
             status: dict | None, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        speed = link["demo_speed"]
        travel = timedelta(seconds=link["one_way_s"] / speed)
        out = {
            "id": next(self._ids),
            "crew_id": crew_id,
            "direction": "to_ground",
            "author": name,
            "day": day,
            "priority": priority,
            "text": text.strip(),
            "sent_at": now.isoformat(),
            "arrives_at": (now + travel).isoformat(),
            "delay_s": link["one_way_s"],
            "status_packet": None if status is None else {
                "overall": status["overall"],
                "counts": status["counts"],
                "flagged": [f'{i["name"]}: {i["value"]} {i["unit"]} ({i["level"]})'
                            for i in status["indicators"] if i["level"] != "normal"],
            },
            "simulated": False,
        }
        out["travel_s"] = travel.total_seconds()
        if self.mode == "live":
            # A person at the console answers; nothing is pre-written.
            with self._lock:
                self.messages.append(out)
            return out
        reply_sent = now + travel + timedelta(seconds=GROUND_HANDLING_S / speed)
        reply = {
            "id": next(self._ids),
            "crew_id": crew_id,
            "direction": "from_ground",
            "author": "Flight surgeon (simulated)",
            "day": day,
            "priority": priority,
            "text": ground_reply(status, name, text, priority, day),
            "sent_at": reply_sent.isoformat(),
            "arrives_at": (reply_sent + travel).isoformat(),
            "delay_s": link["one_way_s"],
            "status_packet": None,
            "simulated": True,
            "in_reply_to": out["id"],
        }
        with self._lock:
            self.messages += [out, reply]
        return out

    # ------------------------------------------------------------ ground (console) side
    def inbox(self, now: datetime | None = None) -> tuple[list[dict], int]:
        """Crew messages that have reached Earth, newest first, with their replies."""
        now = now or datetime.now(timezone.utc)
        out = []
        for m in self.messages:
            if m["direction"] != "to_ground" or datetime.fromisoformat(m["arrives_at"]) > now:
                continue
            replies = [r for r in self.messages if r.get("in_reply_to") == m["id"]]
            out.append({**m, "replies": [{k: r[k] for k in ("id", "author", "text", "sent_at", "arrives_at", "simulated")}
                                         for r in replies]})
        # In transit: the console only knows something is on its way, not what it says.
        in_transit = sum(1 for m in self.messages
                         if m["direction"] == "to_ground" and datetime.fromisoformat(m["arrives_at"]) > now)
        out.sort(key=lambda m: m["arrives_at"], reverse=True)
        return out, in_transit

    def mark_seen(self, msg_id: int, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            m = self._get_arrived(msg_id, now)
            m.setdefault("seen_at", now.isoformat())
            return m

    def reply(self, msg_id: int, text: str, author: str, now: datetime | None = None) -> dict:
        """A person's reply from the console. It travels back with the same one-way delay."""
        now = now or datetime.now(timezone.utc)
        with self._lock:
            m = self._get_arrived(msg_id, now)
            m.setdefault("seen_at", now.isoformat())
            travel = timedelta(seconds=m.get("travel_s", 0.0))
            r = {
                "id": next(self._ids),
                "crew_id": m["crew_id"],
                "direction": "from_ground",
                "author": author,
                "day": m["day"],
                "priority": m["priority"],
                "text": text.strip(),
                "sent_at": now.isoformat(),
                "arrives_at": (now + travel).isoformat(),
                "delay_s": m["delay_s"],
                "status_packet": None,
                "simulated": False,
                "in_reply_to": m["id"],
            }
            self.messages.append(r)
            return r

    def _get_arrived(self, msg_id: int, now: datetime) -> dict:
        for m in self.messages:
            if m["id"] == msg_id and m["direction"] == "to_ground":
                if datetime.fromisoformat(m["arrives_at"]) > now:
                    raise ValueError("That message hasn't reached Earth yet.")
                return m
        raise KeyError(msg_id)

    def thread(self, crew_id: str, now: datetime | None = None) -> list[dict]:
        """The crew member's messages. Ground replies appear only once they've 'arrived'."""
        now = now or datetime.now(timezone.utc)
        result = []
        for m in self.messages:
            if m["crew_id"] != crew_id:
                continue
            arrived = datetime.fromisoformat(m["arrives_at"]) <= now
            if m["direction"] == "from_ground" and not arrived:
                result.append({"id": m["id"], "direction": "from_ground", "pending": True,
                               "in_reply_to": m["in_reply_to"], "arrives_at": m["arrives_at"],
                               "sent_at": m["sent_at"]})
                continue
            result.append({**m, "pending": False, "delivered": arrived})
        return result
