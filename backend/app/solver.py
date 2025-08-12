from typing import List, Dict, Tuple
from datetime import time

# ========================
# Helpers de tiempo
# ========================
def _to_minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    if h == 24 and m == 0:
        return 24*60 - 1  # 23:59 como tope del día
    return h*60 + m

def _slot_dur_minutes(start: str, end: str) -> int:
    return max(0, _to_minutes(end) - _to_minutes(start))

def _parse_time(hhmm: str) -> time:
    h, m = map(int, hhmm.split(":"))
    if h == 24 and m == 0:
        return time(23, 59)
    return time(h, m)

def _slot_hours(start: str, end: str) -> float:
    return _slot_dur_minutes(start, end) / 60.0

# ========================
# Greedy v1 (simple)
# ========================
def greedy_assign(
    slots: List[Dict[str, str]],       # [{"start":"HH:MM","end":"HH:MM"}...]
    min_per_slot: List[int],           # misma longitud que slots
    employees: List[Dict[str, float]], # [{"id":"E1","target_hours":40.0}...]
    tolerance: float = 2.0
):
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

# ========================
# Helpers Greedy v2
# ========================
def _blocks_count(intervals: List[Dict[str, str]]) -> int:
    """Cuenta bloques (segmentos no contiguos) en una lista de intervalos del mismo día."""
    if not intervals:
        return 0
    ivals = sorted(intervals, key=lambda s: _to_minutes(s["start"]))
    blocks = 1
    for i in range(1, len(ivals)):
        prev_end = _to_minutes(ivals[i-1]["end"])
        cur_start = _to_minutes(ivals[i]["start"])
        if prev_end != cur_start:
            blocks += 1
    return blocks

def _is_available(emp: Dict, day: str, start: str, end: str) -> bool:
    av = emp.get("availability", {})
    if day not in av or not av[day]:
        return False
    s = _to_minutes(start); e = _to_minutes(end)
    for rng in av[day]:
        a = _to_minutes(rng["start"]); b = _to_minutes(rng["end"])
        if a <= s and e <= b:
            return True
    return False

# ========================
# Greedy v2 (reglas duras)
# ========================
def greedy_assign_v2(
    slots: List[Dict[str, str]],          # [{"day","start","end"}...]
    min_per_slot: List[int],
    employees: List[Dict],                # cada emp: id, target_hours, max_hours_per_day, max_blocks_per_day, availability
    tolerance: float = 2.0
):
    hours_assigned = {e["id"]: 0.0 for e in employees}
    hours_per_day: Dict[Tuple[str, str], float] = {}                # (emp_id, day) -> horas
    emp_day_intervals: Dict[Tuple[str, str], List[Dict]] = {}       # (emp_id, day) -> intervalos
    assignments: List[List[str]] = [[] for _ in slots]
    warnings: List[str] = []

    for i, need in enumerate(min_per_slot):
        day = slots[i]["day"]
        s = slots[i]["start"]; e = slots[i]["end"]
        dur_h = _slot_dur_minutes(s, e) / 60.0

        attempts = 0
        while len(assignments[i]) < need and attempts < 2000:
            cand: List[tuple] = []
            for emp in employees:
                eid = emp["id"]
                if eid in assignments[i]:
                    continue
                if not _is_available(emp, day, s, e):
                    continue
                current_day_hours = hours_per_day.get((eid, day), 0.0)
                if current_day_hours + dur_h > float(emp.get("max_hours_per_day", 10.0)) + 1e-6:
                    continue
                lst = emp_day_intervals.get((eid, day), [])
                new_lst = lst + [{"start": s, "end": e}]
                if _blocks_count(new_lst) > int(emp.get("max_blocks_per_day", 2)):
                    continue
                cont = 0
                for itv in lst:
                    if itv["end"] == s or itv["start"] == e:
                        cont = 1; break
                remaining = float(emp["target_hours"]) - hours_assigned[eid]
                cand.append((cont, remaining, eid))

            if not cand:
                warnings.append(f"Sin candidatos válidos para {day} {s}-{e}; franja queda corta")
                break

            cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
            chosen_id = cand[0][2]

            assignments[i].append(chosen_id)
            hours_assigned[chosen_id] += dur_h
            hours_per_day[(chosen_id, day)] = hours_per_day.get((chosen_id, day), 0.0) + dur_h
            emp_day_intervals.setdefault((chosen_id, day), []).append({"start": s, "end": e})
            attempts += 1

        if len(assignments[i]) < need:
            warnings.append(f"Déficit en {day} {s}-{e}: {len(assignments[i])}/{need}")

    for emp in employees:
        eid = emp["id"]
        lo = float(emp["target_hours"]) - tolerance
        hi = float(emp["target_hours"]) + tolerance
        if not (lo <= hours_assigned[eid] <= hi):
            warnings.append(f"AVISO {eid}: {hours_assigned[eid]:.1f}h vs objetivo {emp['target_hours']}±{tolerance}")

    return assignments, hours_assigned, warnings
