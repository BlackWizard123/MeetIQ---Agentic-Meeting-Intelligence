
<img width="3464" height="1074" alt="Picsart_26-04-08_17-08-13-016" src="https://github.com/user-attachments/assets/e4d69e92-997b-497b-a97c-bfe52801df95" />

# H2S x Google GenAIAPAC Cohort 1 Hackathon

# 🗓️ MeetIQ — Meeting Intelligence Platform
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![GCP](https://img.shields.io/badge/Google%20Cloud-GCP-blue?logo=googlecloud)
![Cloud Run](https://img.shields.io/badge/Cloud%20Run-Serverless-4285F4?logo=googlecloud)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql)
![GCS](https://img.shields.io/badge/Cloud%20Storage-GCS-orange?logo=googlecloud)
![Gemini](https://img.shields.io/badge/Vertex%20AI-Gemini-purple?logo=google)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?logo=docker)

> A multi-agent AI system that transforms meeting transcripts into structured memos, smart task assignments, scheduled calendar events, and living project dashboards — built on Google Cloud Platform.

### ➡️ Demo video link :  https://www.youtube.com/watch?v=jdCALd0zPkI
### ➡️ Medium Article : https://hariharanc0912.medium.com/the-real-work-shouldnt-start-when-the-meeting-ends-how-we-automated-post-meeting-chaos-with-ai-a8b8f37177df
---

## What is MeetIQ?

MeetIQ is an AI-powered meeting intelligence platform designed for project managers who run multiple teams. Upload a `.txt` meeting transcript and MeetIQ automatically:

- Extracts a **detailed meeting memo** with decisions, blockers, risks, highlights, and manager actions
- Generates **smart action items** assigned to team members based on their skills, level, and current workload
- Suggests **follow-up meetings** and schedules them directly to **Google Calendar**
- Creates **Google Tasks** for every action item under the manager's account
- Updates a **Google Sheets Meeting Log** with structured, color-coded data
- Maintains a **live Task Tracker sheet** per project showing every employee's workload
- Generates **meeting briefings** before check-ins so the manager knows what to expect
- Provides a **Task Tracker UI** to update task statuses and sync to Sheets

---

## Architecture

<img width="1031" height="822" alt="meetiq-arch" src="https://github.com/user-attachments/assets/7569f6e2-a288-4028-98f0-ea7acfe99587" />


```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/CSS/JS)                │
│  Upload → Review (Memo/Tasks/Meetings) → Schedule → Track   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend                           │
│                                                             │
│  ┌─────────────┐  ┌──────────────────────────────────────┐  │
│  │ Orchestrator│  │           AI Agents                  │  │
│  │  (main.py)  │→ │  Memo │ Task │ Meeting │ Thread      │  │
│  └─────────────┘  └──────────────────────────────────────┘  │
│         │                      │                            │
│         │              Vertex AI (Gemini 1.5)               │
│         │                                                   │
│  ┌──────▼──────────────────────────────────────────────┐    │
│  │              Services Layer                          │    │
│  │  calendar_service │ sheets_service │ storage_service │    │
│  └──────┬──────────────────┬──────────────────┬────────┘    │
└─────────┼──────────────────┼──────────────────┼────────────┘
          │                  │                  │
    ┌─────▼──────┐   ┌───────▼──────┐  ┌───────▼────────┐
    │ Cloud SQL  │   │ Google APIs  │  │   GCS Bucket   │
    │ PostgreSQL │   │ Calendar     │  │  meetiq-data   │
    │            │   │ Tasks        │  │  (JSON store)  │
    │ employees  │   │ Sheets       │  │                │
    │ projects   │   │ Drive        │  │ meetings/*.json│
    │ tasks      │   └──────────────┘  │ history.json  │
    └────────────┘                     └────────────────┘
```

---
## 🚀 Technologies & Services Used

### 🧠 AI & Intelligence
- Vertex AI (Gemini 2.5 Flash & Pro) — Multi-agent reasoning and generation

### ⚙️ Backend
- FastAPI — High-performance API framework
- Python 3.12 — Core backend language

### ☁️ Google Cloud Platform
- Cloud Run — Serverless deployment
- Cloud SQL (PostgreSQL) — Relational data storage
- Cloud Storage (GCS) — Persistent JSON storage
- Secret Manager — Secure credential storage
- Cloud Build — CI/CD pipeline
- Container Registry — Docker image storage

### 🔗 Google Workspace Integration
- Google Sheets API — Meeting logs & task tracker
- Google Calendar API — Event scheduling
- Google Tasks API — Task reminders
- Google Drive API — File discovery

### 🗄️ Data & Storage
- PostgreSQL — Employees, projects, tasks
- JSON (GCS) — Meeting transcripts & structured outputs

### 🎨 Frontend
- HTML, CSS, JavaScript — UI & interactions

---

## Multi-Agent System

MeetIQ uses 4 specialized AI agents, each powered by a different Gemini model to distribute load and optimize cost:

| Agent | Model | Responsibility |
|---|---|---|
| **Memo Agent** | Gemini 1.5 Pro | Extracts structured memo — summary points, decisions, blockers, risks, manager actions, highlights |
| **Task Agent** | Gemini 1.5 Flash | Extracts action items with smart assignment — matches tasks to employee skills, suggests guides and companions |
| **Meeting Agent** | Gemini 1.5 Flash | Identifies follow-up meetings needed — suggests date, duration, recipients, agenda |
| **Thread Agent** | Gemini 1.5 Pro | Generates pre-meeting briefings — what was discussed, what to follow up, team status table |

### Smart Task Assignment Logic

When extracting tasks, the Task Agent receives the full employee roster with skills, level, band, and current workload. It then:

1. Matches task requirements to employee skills
2. If assignee is Associate (L1/L2) and task requires skills they lack → assigns a Senior/Lead as **Guide**
3. If task is complex → assigns a peer-level **Companion**
4. Shows current workload (🔴 >80%, 🟡 >40%, 🟢 <40%) to prevent over-assignment
5. Flags skill match as Full / Partial / None

---

## Database Schema (Cloud SQL PostgreSQL)

```sql
-- Projects table
CREATE TABLE projects (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Employees table
CREATE TABLE employees (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    role       TEXT,           -- e.g. "Backend Developer"
    band       TEXT,           -- e.g. "Senior Developer"
    level      TEXT,           -- L1 to L5
    skills     TEXT[],         -- PostgreSQL array
    project_id INTEGER REFERENCES projects(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tasks table (live tracker)
CREATE TABLE tasks (
    id                     SERIAL PRIMARY KEY,
    title                  TEXT NOT NULL,
    project_id             INTEGER REFERENCES projects(id),
    meeting_id             TEXT,           -- links to GCS JSON
    assignee_id            INTEGER REFERENCES employees(id),
    companion_id           INTEGER REFERENCES employees(id),
    guide_id               INTEGER REFERENCES employees(id),
    checker_id             INTEGER REFERENCES employees(id),
    status                 TEXT DEFAULT 'pending',   -- pending/in-progress/done
    priority               TEXT DEFAULT 'Medium',    -- High/Medium/Low
    assigned_date          DATE,
    due_date               DATE,
    total_days             INTEGER,
    notes                  TEXT,
    escalation_details     TEXT,
    current_tasks_snapshot JSONB,   -- snapshot of assignee's workload at assignment time
    created_at             TIMESTAMP DEFAULT NOW(),
    completed_at           TIMESTAMP
);
```

---

## Storage Architecture

### Google Cloud Storage (GCS)

Bucket: `meetiq-data`

```
meetiq-data/
├── history.json              # Index of all processed meetings
└── meetings/
    ├── abc12345.json         # Full meeting record (memo + tasks + meetings + briefing)
    ├── def67890.json
    └── ...
```

Each meeting JSON:
```json
{
  "id": "abc12345",
  "timestamp": "2026-04-08T10:30:00",
  "memo": { "title": "...", "summary_points": [...], "decisions": [...] },
  "tasks": [{ "id": "t1", "title": "...", "assignee": "..." }],
  "meetings": [{ "id": "m1", "title": "...", "suggested_date": "..." }],
  "briefing": { ... }   // cached after first generation
}
```

### Google Sheets (Static — created once by setup_sheets.py)

| Sheet | Purpose | Tabs |
|---|---|---|
| `Meeting Log — Enterprise RAG` | Append-only meeting records | Overview, Tasks, Meetings |
| `Task Tracker — Enterprise RAG` | Live employee workload | Task Tracker, Completed Tasks |
| `Meeting Log — Plipkary` | Append-only meeting records | Overview, Tasks, Meetings |
| `Task Tracker — Plipkary` | Live employee workload | Task Tracker, Completed Tasks |

---

## GCP Services Used

| Service | Purpose |
|---|---|
| **Cloud Run** | Hosts the FastAPI application — serverless, auto-scales |
| **Cloud SQL (PostgreSQL)** | Employees, projects, tasks — relational data |
| **Cloud Storage (GCS)** | Meeting JSON files — persistent across deployments |
| **Vertex AI (Gemini)** | Powers all 4 AI agents |
| **Secret Manager** | Stores all secrets — DB password, Sheet IDs, OAuth tokens |
| **Container Registry** | Stores Docker images built by Cloud Build |
| **Cloud Build** | CI/CD pipeline — builds and deploys on push |
| **Google Calendar API** | Creates meeting events on manager's calendar |
| **Google Tasks API** | Creates task reminders on manager's account |
| **Google Sheets API** | Updates meeting log and task tracker sheets |
| **Google Drive API** | Locates sheets by name |

---

## Project Structure

```
meeting-intelligence/
├── backend/
│   ├── main.py                      # FastAPI app — all endpoints
│   ├── database.py                  # Cloud SQL connection + table init
│   ├── seed.py                      # Seeds dummy employees and projects
│   ├── setup_sheets.py              # One-time Google Sheets setup
│   ├── fix_history.py               # Migration: fix project field in history
│   ├── generate_token.py            # One-time OAuth token generation
│   ├── requirements.txt
│   ├── .env                         # Local only — never commit
│   ├── agents/
│   │   ├── memo_agent.py            # Meeting memo extraction
│   │   ├── task_agent.py            # Smart task extraction + assignment
│   │   ├── meeting_agent.py         # Follow-up meeting suggestions
│   │   └── thread_agent.py          # Pre-meeting briefing generation
│   ├── services/
│   │   ├── groq_client.py           # Vertex AI Gemini wrapper (named groq_client for compatibility)
│   │   ├── calendar_service.py      # Google Calendar + Tasks integration
│   │   ├── sheets_service.py        # Google Sheets integration (static sheets)
│   │   └── storage_service.py       # GCS-backed JSON storage
│   ├── routers/
│   │   └── projects.py              # Project and employee endpoints
│   └── data/                        # Local fallback (dev only)
├── frontend/
│   ├── index.html                   # Single-page application
│   ├── style.css                    # Dark/Light/Google Workspace themes
│   └── app.js                       # All UI logic
├── Dockerfile
├── cloudbuild.yaml
└── .env.example
```

---

## Low Level Architecture Diagram

<img width="1538" height="614" alt="mermaid-diagram" src="https://github.com/user-attachments/assets/230bb505-b750-49e7-b5e2-107d97eb708b" />

---

## How to Run Locally

### Prerequisites
- Python 3.12+
- Google Cloud SDK (`gcloud`)
- A GCP project with billing enabled
- PostgreSQL on Cloud SQL

### Step 1 — Clone and install

```bash
git clone https://github.com/yourusername/meeting-intelligence.git
cd meeting-intelligence/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2 — GCP Setup

```bash
# Login
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  calendar-json.googleapis.com \
  sheets.googleapis.com \
  drive.googleapis.com \
  secretmanager.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com
```

### Step 3 — Create GCS Bucket

```bash
gsutil mb -l us-central1 gs://meetiq-data
gsutil uniformbucketlevelaccess set on gs://meetiq-data
```

### Step 4 — Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

### Step 5 — Generate Google OAuth token

```bash
# Download credentials.json from GCP Console → APIs → Credentials → OAuth 2.0 Client
# Place in backend/
python generate_token.py
# Follow URL in terminal, paste auth code back
```

### Step 6 — Initialize database and seed data

```bash
python seed.py
```

### Step 7 — Create static Google Sheets

```bash
python setup_sheets.py
# Copy printed Sheet IDs into your .env
```

### Step 8 — Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
# Open http://localhost:8080
```

---

## Deploy to Cloud Run

### Step 1 — Create Service Account

```bash
gcloud iam service-accounts create meetiq-sa \
  --display-name="MeetIQ Service Account"

# Grant roles
for role in \
  roles/cloudsql.client \
  roles/storage.objectAdmin \
  roles/aiplatform.user \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:meetiq-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="$role"
done
```

### Step 2 — Store secrets in Secret Manager

```bash
# Store each secret (replace values with yours)
for secret in \
  "DB_HOST=YOUR_DB_IP" \
  "DB_PASSWORD=YOUR_PASSWORD" \
  "MANAGER_EMAIL=YOUR_GMAIL" \
  "SHEET_LOG_RAG=YOUR_SHEET_ID" \
  "SHEET_TRACKER_RAG=YOUR_SHEET_ID" \
  "SHEET_LOG_PLIPKARY=YOUR_SHEET_ID" \
  "SHEET_TRACKER_PLIPKARY=YOUR_SHEET_ID" \
  "GCS_BUCKET=meetiq-data"; do
  key="${secret%%=*}"
  val="${secret#*=}"
  echo -n "$val" | gcloud secrets create "$key" --data-file=-
done

# Store token.json as a secret
gcloud secrets create GOOGLE_TOKEN \
  --data-file=token.json
```

### Step 3 — Build and deploy

```bash
# From project root
gcloud builds submit --config cloudbuild.yaml
```

### Step 4 — Get your URL

```bash
gcloud run services describe meetiq \
  --region=us-central1 \
  --format='value(status.url)'
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/process-transcript` | Upload .txt → run all agents |
| `POST` | `/api/finalize` | Save confirmed memo/tasks/meetings |
| `POST` | `/api/schedule` | Push to Google Calendar + Tasks |
| `GET` | `/api/history` | All past meetings (sidebar) |
| `GET` | `/api/history/{id}` | Meeting briefing (cached) |
| `GET` | `/api/transcript/{id}` | Full meeting detail |
| `GET` | `/api/projects` | All projects |
| `GET` | `/api/projects/{id}/employees` | Employees with workload |
| `GET` | `/api/projects/{id}/tasks` | All tasks for project |
| `PUT` | `/api/tasks/{id}` | Update task status |
| `GET` | `/api/sheet-links` | Google Sheet URLs per project |

---

## Features

### 1. Transcript Processing
Upload any `.txt` meeting transcript. Four AI agents run in sequence extracting structured data with today's date injected to ensure correct year in all outputs.

### 2. Editable Review Flow
Three-step confirmation — Memo → Tasks → Meetings. Every field is editable before anything is committed. Manager has full control.

### 3. Smart Task Assignment
Employees shown with live workload indicators (🔴🟡🟢). Guide suggested when skill mismatch detected. Companion suggested for complex tasks. Current tasks snapshot saved at assignment time for audit trail.

### 4. Google Calendar Integration
Meetings created with datetime picker — manager picks exact date and time. Events appear in manager's Google Calendar with full agenda and participant list in description. Timezone set to Asia/Kolkata (IST).

### 5. Google Sheets — Meeting Log
Append-only log per project. New rows added for every finalized meeting. Priority color-coded in Tasks tab. Auto-resized columns.

### 6. Google Sheets — Task Tracker
One row per employee, updated in-place. Shows up to 3 active tasks per employee. Completed tasks move to Completed tab with grey formatting. Workload % highlighted with traffic-light colors.

### 7. Meeting Briefing
AI-generated pre-meeting briefing with team status table showing every employee's current tasks, completed tasks, workload level, and flag (Overloaded / On Track / Free / Blocked). Cached after first generation — instant on repeat views. Refresh button forces regeneration.

### 8. Task Tracker UI
Lists all tasks per project fetched from Cloud SQL. Editable status and notes inline. Update Sheet button syncs changes back to Google Sheets Task Tracker with loading state.

### 9. Transcript Library
All processed transcripts organized by project. Click any transcript to see full memo detail, tasks table, and scheduled meetings in a clean read-only view.

### 10. Theme System
Three themes — Dark (default), Light, and Google Workspace. Stored in localStorage. Accessible via profile menu at the bottom of the sidebar.

---

## Team

Built for the GCP Hackathon — Cohort 1
