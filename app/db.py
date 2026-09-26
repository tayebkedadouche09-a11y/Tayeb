import sqlite3
from pathlib import Path
DB = Path(__file__).resolve().parent / "tayeb.db"

def connect():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS projects(
          id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
          client TEXT, location TEXT, contract_value REAL DEFAULT 0,
          start_date TEXT, end_date TEXT, status TEXT DEFAULT 'Planning',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          name TEXT NOT NULL,start_date TEXT,end_date TEXT,progress REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS boq(
          id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          code TEXT NOT NULL,description TEXT NOT NULL,unit TEXT,quantity REAL,unit_rate REAL,
          category TEXT, UNIQUE(project_id,code));
        CREATE TABLE IF NOT EXISTS resources(
          id INTEGER PRIMARY KEY,kind TEXT NOT NULL,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,
          unit TEXT,unit_cost REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS daily_reports(
          id INTEGER PRIMARY KEY,project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          report_date TEXT NOT NULL,summary TEXT,progress_percent REAL,labour_count INTEGER,
          material_cost REAL,equipment_cost REAL,notes TEXT);
        CREATE TABLE IF NOT EXISTS billings(
          id INTEGER PRIMARY KEY,project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          invoice_no TEXT UNIQUE NOT NULL,gross_amount REAL,retention_percent REAL,
          tax_amount REAL,status TEXT DEFAULT 'Draft');
        CREATE TABLE IF NOT EXISTS bim_jobs(
          id INTEGER PRIMARY KEY,project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          source_type TEXT,source_uri TEXT,job_type TEXT,status TEXT DEFAULT 'Queued',
          result_json TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit_log(
          id INTEGER PRIMARY KEY,action TEXT,entity TEXT,entity_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
