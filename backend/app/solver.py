from typing import List, Dict, Tuple
from datetime import time

# ===== Helpers de tiempo =====
def _to_minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    if h == 24 and m == 0:
        return 24*60 - 1
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

# ===== Greedy v1 (simple) =====
def greedy_assign(slots: List[Dict[str, str]], min_per_slot: List[int],
                  employees: List[Dict[str, float]], tolerance: float = 2.0):
    dur = [_slot_hours(s["start"], s["end"]) for s in slots]
    hours_assigned = {e["id"]: 0.0 for e in employees}
    assignments: List[List[str]] = [[] for _ in slots]

    for i, need in enumerate(min_per_slot):
        attempts = 0
        while len(assignments[i]) < need and attempts < 1000:
            candidates = sorted(
                employees,
                key=lambda e: (e["target_hours"] - hours_assigned[e["id"]]),
                reverse=True
            )
            picked = None
            for c in candidates:
                remaining = c["target_hours"] - hours_assigned[c["id"]]
                if remaining + tolerance >= dur[i]:
                    picked = c
                    break
            if picked is None:
                picked = max(
                    employees,
                    key=lambda e: (e["target_hours"] - hours_assigned[e["id"]])
                )
            assignments[i].append(picked["id"])
            hours_assigned[picked["id"]] += dur[i]
            attempts += 1
    return assignments, hours_assigned

# ===== Helpers v2 =====
def _merge_contiguous(intervals: List[Dict[str, str]]) -> List[Tuple[int, int]]:
    """Une intervalos contiguos (end == next start). Devuelve en minutos."""
    if not intervals: return []
    ivals = sorted([( _to_minutes(x["start"]), _to_minutes(x["end"]) ) for x in intervals])
    merged = [ivals[0]]
    for s,e in ivals[1:]:
        ps,pe = merged[-1]
        if pe == s:  # contiguo → mismo bloque
            merged[-1] = (ps, e)
        elif e <= pe:  # contenido
            continue
        else:
            merged.append((s,e))
    return merged

def _blocks_count(intervals: List[Dict[str, str]]) -> int:
    return len(_merge_contiguous(intervals))

def _gap_ok(intervals: List[Dict[str, str]], min_rest_h: float) -> bool:
    """Si hay >1 bloque, todos los huecos entre bloques deben ser >= min_rest."""
    merged = _merge_contiguous(intervals)
    if len(merged) <= 1: return True
    min_rest_min = int(min_rest_h * 60)
    for i in range(1, len(merged)):
        gap = merged[i][0] - merged[i-1][1]
        if gap < min_rest_min:
            return False
    return True

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

# ===== Greedy v2 con reglas duras (ampliado) =====
def greedy_assign_v2(
    slots: List[Dict[str, str]],          # [{"day","start","end"}...]
    min_per_slot: List[int],
    employees: List[Dict],                # id, target_hours, max_hours_per_day, max_blocks_per_day, min_hours_per_day, min_rest_between_blocks, availability
    tolerance: float = 2.0
):
    hours_assigned = {e["id"]: 0.0 for e in employees}
    hours_per_day: Dict[Tuple[str, str], float] = {}          # (emp_id, day) -> horas
    emp_day_intervals: Dict[Tuple[str, str], List[Dict]] = {} # (emp_id, day) -> intervalos
    assignments: List[List[str]] = [[] for _ in slots]
    warnings: List[str] = []

    for i, need in enumerate(min_per_slot):
        day = slots[i]["day"]; s = slots[i]["start"]; e = slots[i]["end"]
        dur_h = _slot_dur_minutes(s, e) / 60.0

        attempts = 0
        while len(assignments[i]) < need and attempts < 2000:
            cand: List[tuple] = []
            for emp in employees:
                eid = emp["id"]
                if eid in assignments[i]: continue
                if not _is_available(emp, day, s, e): continue

                current_day_hours = hours_per_day.get((eid, day), 0.0)
                max_day = float(emp.get("max_hours_per_day", 10.0))
                if current_day_hours + dur_h > max_day + 1e-6:
                    continue

                # bloques + descanso entre bloques
                lst = emp_day_intervals.get((eid, day), [])
                new_lst = lst + [{"start": s, "end": e}]
                max_blocks = int(emp.get("max_blocks_per_day", 2))
                if _blocks_count(new_lst) > max_blocks:
                    continue
                min_rest = float(emp.get("min_rest_between_blocks", 0.0))
                if not _gap_ok(new_lst, min_rest):
                    continue

                # Heurística leve para min horas/día:
                # si aún no trabaja ese día y este slot es menor al mínimo, lo permitimos
                # pero luego avisaremos si acaba el día por debajo.
                # (Implementación estricta requeriría lookahead global.)
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

    # Avisos por objetivo semanal ± tolerancia y por mínimos diarios
    for emp in employees:
        eid = emp["id"]
        lo = float(emp["target_hours"]) - tolerance
        hi = float(emp["target_hours"]) + tolerance
        if not (lo <= hours_assigned[eid] <= hi):
            warnings.append(f"AVISO {eid}: {hours_assigned[eid]:.1f}h vs objetivo {emp['target_hours']}±{tolerance}")

    # Mínimo diario si trabajaron ese día
    for emp in employees:
        eid = emp["id"]
        min_day = float(emp.get("min_hours_per_day", 0.0))
        for day in {s["day"] for s in slots}:
            h = hours_per_day.get((eid, day), 0.0)
            if 1e-6 < h < min_day - 1e-6:
                warnings.append(f"AVISO {eid} {day}: {h:.1f}h < mínimo diario {min_day}h")

    return assignments, hours_assigned, warnings
