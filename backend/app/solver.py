# backend/app/solver.py
from datetime import time
from typing import List, Dict, Tuple

def _parse_time(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(hour=int(h), minute=int(m))

def _slot_hours(start: str, end: str) -> float:
    a = _parse_time(start)
    b = _parse_time(end)
    return ((b.hour*60 + b.minute) - (a.hour*60 + a.minute)) / 60.0

def greedy_assign(
    slots: List[Dict[str, str]],       # [{"start":"HH:MM","end":"HH:MM"}...]
    min_per_slot: List[int],           # misma longitud que slots
    employees: List[Dict[str, float]], # [{"id":"E1","target_hours":40.0}...]
    tolerance: float = 2.0
):
    """Asigna mínimos por franja priorizando quien tiene más horas restantes."""
    dur = [_slot_hours(s["start"], s["end"]) for s in slots]
    hours_assigned = {e["id"]: 0.0 for e in employees}
    assignments: List[List[str]] = [[] for _ in slots]

    for i, need in enumerate(min_per_slot):
        attempts = 0
        while len(assignments[i]) < need and attempts < 1000:
            # ordenar por horas restantes (objetivo - asignadas), desc
            candidates = sorted(
                employees,
                key=lambda e: (e["target_hours"] - hours_assigned[e["id"]]),
                reverse=True
            )
            picked = None
            for c in candidates:
                remaining = c["target_hours"] - hours_assigned[c["id"]]
                # permitimos pasarnos hasta 'tolerance' horas
                if remaining + tolerance >= dur[i]:
                    picked = c
                    break
            if picked is None:
                # si nadie tiene margen, elige el que menos se pasa
                picked = max(
                    employees,
                    key=lambda e: (e["target_hours"] - hours_assigned[e["id"]])
                )
            assignments[i].append(picked["id"])
            hours_assigned[picked["id"]] += dur[i]
            attempts += 1

    return assignments, hours_assigned
