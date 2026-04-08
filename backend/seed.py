"""
Run once: python seed.py
Seeds projects and employees into Cloud SQL.
"""
from database import get_conn, get_cursor, init_db

PROJECTS = [
    {"name": "Enterprise RAG",  "description": "Enterprise Retrieval-Augmented Generation platform for internal knowledge management"},
    {"name": "Plipkary",        "description": "Full-stack e-commerce platform with real-time inventory and payments"},
]

EMPLOYEES = [
    # ── Enterprise RAG ──────────────────────────────────────────────────
    {"name": "Arjun",   "email": "arjun.rag@dummyteam.com",    "role": "Backend Developer",            "band": "Senior Developer",  "level": "L3", "skills": ["Python","FastAPI","LangChain","PostgreSQL","RAG"],    "project": "Enterprise RAG"},
    {"name": "Sneha",   "email": "sneha.rag@dummyteam.com",    "role": "ML Engineer",                  "band": "Senior Developer",  "level": "L3", "skills": ["Python","RAG","Embeddings","Vector DB","LLMs"],        "project": "Enterprise RAG"},
    {"name": "Karthik", "email": "karthik.rag@dummyteam.com",  "role": "Associate Backend Developer",  "band": "Associate",         "level": "L2", "skills": ["Python","REST APIs","FastAPI"],                         "project": "Enterprise RAG"},
    {"name": "Divya",   "email": "divya.rag@dummyteam.com",    "role": "Frontend Developer",           "band": "Senior Developer",  "level": "L3", "skills": ["React","TypeScript","CSS","UI/UX"],                    "project": "Enterprise RAG"},
    {"name": "Rahul",   "email": "rahul.rag@dummyteam.com",    "role": "Associate Frontend Developer", "band": "Associate",         "level": "L2", "skills": ["HTML","CSS","JavaScript","React"],                     "project": "Enterprise RAG"},
    {"name": "Meena",   "email": "meena.rag@dummyteam.com",    "role": "QA Engineer",                  "band": "Associate",         "level": "L2", "skills": ["Testing","Selenium","Pytest","API Testing"],           "project": "Enterprise RAG"},

    # ── Plipkary ────────────────────────────────────────────────────────
    {"name": "Vikram",  "email": "vikram.plip@dummyteam.com",  "role": "Backend Developer",            "band": "Senior Developer",  "level": "L3", "skills": ["Node.js","PostgreSQL","Redis","REST APIs"],            "project": "Plipkary"},
    {"name": "Priya",   "email": "priya.plip@dummyteam.com",   "role": "Frontend Developer",           "band": "Senior Developer",  "level": "L3", "skills": ["React","Next.js","Tailwind","TypeScript"],             "project": "Plipkary"},
    {"name": "Arun",    "email": "arun.plip@dummyteam.com",    "role": "Associate Backend Developer",  "band": "Associate",         "level": "L2", "skills": ["Node.js","REST APIs","Express"],                       "project": "Plipkary"},
    {"name": "Nithya",  "email": "nithya.plip@dummyteam.com",  "role": "Associate Frontend Developer", "band": "Associate",         "level": "L2", "skills": ["React","CSS","JavaScript"],                           "project": "Plipkary"},
    {"name": "Suresh",  "email": "suresh.plip@dummyteam.com",  "role": "DevOps Engineer",              "band": "Lead",              "level": "L4", "skills": ["Docker","GCP","Cloud Run","CI/CD","Kubernetes"],       "project": "Plipkary"},
    {"name": "Lakshmi", "email": "lakshmi.plip@dummyteam.com", "role": "QA Engineer",                  "band": "Associate",         "level": "L2", "skills": ["Testing","Cypress","Jest","E2E Testing"],             "project": "Plipkary"},
]

def seed():
    init_db()
    conn = get_conn()
    cur  = get_cursor(conn)

    # Seed projects
    project_ids = {}
    for p in PROJECTS:
        cur.execute("""
            INSERT INTO projects (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
        """, (p["name"], p["description"]))
        project_ids[p["name"]] = cur.fetchone()["id"]

    # Seed employees
    for e in EMPLOYEES:
        pid = project_ids[e["project"]]
        cur.execute("""
            INSERT INTO employees (name, email, role, band, level, skills, project_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                name=EXCLUDED.name, role=EXCLUDED.role,
                band=EXCLUDED.band, level=EXCLUDED.level,
                skills=EXCLUDED.skills, project_id=EXCLUDED.project_id
        """, (e["name"], e["email"], e["role"], e["band"], e["level"], e["skills"], pid))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Seed complete — projects and employees inserted")

if __name__ == "__main__":
    seed()