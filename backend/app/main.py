from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict
from datetime import time
import os

app = FastAPI(title="Cuadrantes Hostelería", version="0.1.0")

# ---------- Servir la mini UI ----------
# Carpeta estática: backend/app/static  (ahí va tu index.html)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
def home():
    index_path = os.path.join("app", "static", "index.html")
    return FileResponse(index_path)

# ---------- Helpers ----------
def _parse_time(hhmm: str) -> time:
    h, m = map(int, hhmm.split(":"))
    # Permitir "24:00" (lo mapeamos a 23:59 para evitar error en datetime.time)
    if h == 24 and m == 0:
        return time(23, 59)
    return time(hour=h, minute=m)

def _to_str(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

def _slot_hours(start: str, end: str) -> float:
    a = _parse_time(start)
    b = _parse_time(end)
    return ((b.hour*60 + b.minute) - (a.hour*60 + a.minute)) / 60.0

# ---------- Modelos ----------
class GenerateSlotsRequest(BaseModel):
    marks: List[str]            # ["11:00","13:00","16:00","18:00","20:00","24:00"]
    adjacent_only: bool = True

class Slot(BaseModel):
    start: str  # "HH:MM"
    end: str    # "HH:MM"

class EmployeeIn(BaseModel):
    id: str
    target_hours: float

class GreedySolveRequest(BaseModel):
    slots: List[Slot]
    min_per_slot: List[int]
    employees: List[EmployeeIn]
    tolerance: float = 2.0

class GreedySolveResponse(BaseModel):
    assignments: List[List[str]]
    hours_assigned: Dict[str, float]

# ---------- Endpoints básicos ----------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/slots/generate")
def generate_slots(payload: GenerateSlotsRequest):
    marks = sorted({_parse_time(x) for x in payload.marks}, key=lambda t: (t.hour, t.minute))
    if len(marks) < 2:
        return {"slots": []}

    slots = []
    # adyacentes
    for i in range(len(marks) - 1):
        slots.append({"start": _to_str(marks[i]), "end": _to_str(marks[i+1])})
    # combinadas
    if not payload.adjacent_only:
        for i in range(len(marks) - 2):
            for j in range(i + 2, len(marks)):
                slots.append({"start": _to_str(marks[i]), "end": _to_str(marks[j])})

    # dedup
    seen = set()
    unique = []
    for s in slots:
        key = (s["start"], s["end"])
        if key not in seen:
            seen.add(key); unique.append(s)
    return {"slots": unique}

# ---------- Algoritmo mínimo (greedy) ----------
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

@app.post("/solve/greedy", response_model=GreedySolveResponse)
def solve_greedy(payload: GreedySolveRequest):
    if len(payload.slots) != len(payload.min_per_slot):
        raise HTTPException(status_code=400, detail="slots y min_per_slot deben tener la misma longitud")

    slots = [{"start": s.start, "end": s.end} for s in payload.slots]
    employees = [{"id": e.id, "target_hours": e.target_hours} for e in payload.employees]

    assignments, hours_assigned = greedy_assign(
        slots=slots,
        min_per_slot=payload.min_per_slot,
        employees=employees,
        tolerance=payload.tolerance,
    )
    return {"assignments": assignments, "hours_assigned": hours_assigned}
