# Tayeb Construction ERP — application layer

This is the Tayeb-owned application layer. It is intentionally written as new code and connects the construction workflows represented by the reference components without copying their implementation.

## Modules
- Projects, phases, tasks and progress
- BOQ, quantities, rate analysis and estimates
- Materials, labour and equipment
- Site daily reports and consumption
- Procurement and subcontractor controls
- Progress billing / IPC, retention and cash flow
- BIM/takeoff job boundary
- Role-aware API and audit trail

## Run
```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000
