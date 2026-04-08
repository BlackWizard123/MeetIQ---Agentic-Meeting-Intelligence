import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "meetingdb"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def get_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)

def init_db():
    conn = get_conn()
    cur  = get_cursor(conn)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at  TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS employees (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            email        TEXT NOT NULL UNIQUE,
            role         TEXT,
            band         TEXT,
            level        TEXT,
            skills       TEXT[],
            project_id   INTEGER REFERENCES projects(id),
            created_at   TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id                      SERIAL PRIMARY KEY,
            title                   TEXT NOT NULL,
            project_id              INTEGER REFERENCES projects(id),
            meeting_id              TEXT,
            assignee_id             INTEGER REFERENCES employees(id),
            companion_id            INTEGER REFERENCES employees(id),
            guide_id                INTEGER REFERENCES employees(id),
            checker_id              INTEGER REFERENCES employees(id),
            status                  TEXT DEFAULT 'pending',
            priority                TEXT DEFAULT 'Medium',
            assigned_date           DATE,
            due_date                DATE,
            total_days              INTEGER,
            notes                   TEXT,
            escalation_details      TEXT,
            current_tasks_snapshot  JSONB,
            created_at              TIMESTAMP DEFAULT NOW(),
            completed_at            TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database tables initialized")