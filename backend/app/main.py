from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import time
from app.solver import greedy_assign

app = FastAPI(title="Cuadrantes Hostelería", version="0.1.0")

# -------- helpers para /slots/generate --------
class GenerateSlotsRequest(BaseModel):
    marks: List[str]            # ["11:00","13:00","16:00","18:00","20:00","24:00"]
    adjacent_only: bool = True

def _parse_time(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(hour=int(h), minute=int(m))

def _to_str(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/slots/generate")
def generate_slots(payload: GenerateSlotsRequest):
    marks = sorted({_parse_time(x) for x in payload.marks}, key=lambda t: (t.hour, t.minute))
    if len(marks) < 2:
        return {"slots": []}

    slots = []
    for i in range(len(marks) - 1):
        slots.append({"start": _to_str(marks[i]), "end": _to_str(marks[i+1])})

    if not payload.adjacent_only:
        for i in range(len(marks) - 2):
            for j in range(i + 2, len(marks)):
                slots.append({"start": _to_str(marks[i]), "end": _to_str(marks[j])})

    seen = set()
    unique = []
    for s in slots:
        key = (s["start"], s["end"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return {"slots": unique}

# -------- modelos y endpoint del solver --------
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
