from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from datetime import time

app = FastAPI(title="Cuadrantes Hostelería", version="0.1.0")

class GenerateSlotsRequest(BaseModel):
    marks: List[str]            # horas "HH:MM", ej: ["11:00","13:00","16:00","18:00","20:00","24:00"]
    adjacent_only: bool = True  # si False, generará también combinaciones más largas

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
    # adyacentes (11-13, 13-16, ...)
    for i in range(len(marks) - 1):
        slots.append({"start": _to_str(marks[i]), "end": _to_str(marks[i+1])})

    # combinadas (11-16, 11-18, ...) si se pide
    if not payload.adjacent_only:
        for i in range(len(marks) - 2):
            for j in range(i + 2, len(marks)):
                slots.append({"start": _to_str(marks[i]), "end": _to_str(marks[j])})

    # dedup por si acaso
    seen = set()
    unique = []
    for s in slots:
        key = (s["start"], s["end"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return {"slots": unique}
