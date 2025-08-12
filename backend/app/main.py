from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict
from datetime import time
import os

# Importa los solvers desde solver.py
from app.solver import greedy_assign, greedy_assign_v2

app = FastAPI(title="Cuadrantes Hostelería", version="0.1.0")

# ---------- Servir la mini UI ----------
# Carpeta estática: backend/app/static  (ahí va tu index.html)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
def home():
    index_path = os.path.join("app", "static", "index.html")
    return FileResponse(index_path, media_type="text/html")

# ---------- Helpers SOLO para /slots/generate ----------
def _parse_time(hhmm: str) -> time:
    h, m = map(int, hhmm.split(":"))
    # Permitir "24:00" (lo mapeamos a 23:59 para evitar error en datetime.time)
    if h == 24 and m == 0:
        return time(23, 59)
    return time(hour=h, minute=m)

def _to_str(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

# ---------- Modelos (v1) ----------
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

# ---------- Endpoint Greedy v1 (simple) ----------
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

# ---------- Modelos (v2 con reglas duras) ----------
class SlotV2(BaseModel):
    day: str     # "Mon","Tue","Wed","Thu","Fri","Sat","Sun" (o "Lun", etc.)
    start: str
    end: str

class EmployeeV2(BaseModel):
    id: str
    target_hours: float
    max_hours_per_day: float = 10.0
    max_blocks_per_day: int = 2
    # {"Mon":[{"start":"11:00","end":"23:59"}], ...}
    availability: Dict[str, List[Dict[str, str]]] = {}

class GreedyV2Request(BaseModel):
    slots: List[SlotV2]
    min_per_slot: List[int]
    employees: List[EmployeeV2]
    tolerance: float = 2.0

class GreedyV2Response(BaseModel):
    assignments: List[List[str]]
    hours_assigned: Dict[str, float]
    warnings: List[str] = []

# ---------- Endpoint Greedy v2 (reglas duras) ----------
@app.post("/solve/greedy_v2", response_model=GreedyV2Response)
def solve_greedy_v2(payload: GreedyV2Request):
    if len(payload.slots) != len(payload.min_per_slot):
        raise HTTPException(status_code=400, detail="slots y min_per_slot deben tener la misma longitud")

    slots = [{"day": s.day, "start": s.start, "end": s.end} for s in payload.slots]
    employees = [{
        "id": e.id,
        "target_hours": e.target_hours,
        "max_hours_per_day": e.max_hours_per_day,
        "max_blocks_per_day": e.max_blocks_per_day,
        "availability": e.availability
    } for e in payload.employees]

    assignments, hours_assigned, warnings = greedy_assign_v2(
        slots=slots,
        min_per_slot=payload.min_per_slot,
        employees=employees,
        tolerance=payload.tolerance
    )
    return {"assignments": assignments, "hours_assigned": hours_assigned, "warnings": warnings}
