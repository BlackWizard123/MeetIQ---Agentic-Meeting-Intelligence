from fastapi import APIRouter, HTTPException
from database import get_conn, get_cursor
import json

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects")
def get_projects():
    conn = get_conn()
    cur  = get_cursor(conn)
    cur.execute("SELECT id, name, description FROM projects ORDER BY name")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


@router.get("/projects/{project_id}/employees")
def get_employees(project_id: int):
    conn = get_conn()
    cur  = get_cursor(conn)

    # Get employees with their current active task count
    cur.execute("""
        SELECT
            e.id, e.name, e.email, e.role, e.band, e.level, e.skills,
            COUNT(t.id) FILTER (WHERE t.status != 'done') AS active_task_count
        FROM employees e
        LEFT JOIN tasks t ON t.assignee_id = e.id AND t.status != 'done'
        WHERE e.project_id = %s
        GROUP BY e.id
        ORDER BY e.name
    """, (project_id,))
    employees = cur.fetchall()

    result = []
    for emp in employees:
        e = dict(emp)
        # Fetch current active tasks for this employee
        cur.execute("""
            SELECT id, title, priority, status, due_date
            FROM tasks
            WHERE assignee_id = %s AND status != 'done'
            ORDER BY priority DESC, due_date ASC
        """, (e["id"],))
        e["current_tasks"] = [dict(t) for t in cur.fetchall()]
        # Workload % — capped at 100, 20% per active task
        e["workload_pct"] = min(100, e["active_task_count"] * 20)
        result.append(e)

    cur.close(); conn.close()
    return result


@router.get("/projects/{project_id}/tasks")
def get_project_tasks(project_id: int):
    """All tasks for a project — used by Task Tracker page."""
    conn = get_conn()
    cur  = get_cursor(conn)
    cur.execute("""
        SELECT
            t.id, t.title, t.status, t.priority,
            t.assigned_date, t.due_date, t.total_days,
            t.notes, t.escalation_details, t.meeting_id,
            t.created_at, t.completed_at,
            a.name  AS assignee_name,  a.email AS assignee_email,
            c.name  AS companion_name,
            g.name  AS guide_name,
            ch.name AS checker_name
        FROM tasks t
        LEFT JOIN employees a  ON a.id  = t.assignee_id
        LEFT JOIN employees c  ON c.id  = t.companion_id
        LEFT JOIN employees g  ON g.id  = t.guide_id
        LEFT JOIN employees ch ON ch.id = t.checker_id
        WHERE t.project_id = %s
        ORDER BY t.created_at DESC
    """, (project_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


@router.put("/tasks/{task_id}")
def update_task_status(task_id: int, body: dict):
    """Update task fields from Task Tracker UI."""
    conn = get_conn()
    cur  = get_cursor(conn)

    allowed = ["status", "priority", "due_date", "notes", "escalation_details"]
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        raise HTTPException(400, "No valid fields to update")

    if updates.get("status") == "done":
        updates["completed_at"] = "NOW()"

    set_clause = ", ".join(
        f"{k} = NOW()" if v == "NOW()" else f"{k} = %s"
        for k, v in updates.items()
    )
    values = [v for v in updates.values() if v != "NOW()"]
    values.append(task_id)

    cur.execute(f"UPDATE tasks SET {set_clause} WHERE id = %s", values)
    conn.commit()
    cur.close(); conn.close()
    return {"status": "updated"}


@router.post("/projects/{project_id}/tasks/save-bulk")
def save_bulk_tasks(project_id: int, body: dict):
    """
    Called after finalize — saves all confirmed tasks to the DB.
    Body: { meeting_id, tasks: [...] }
    """
    conn = get_conn()
    cur  = get_cursor(conn)
    meeting_id = body.get("meeting_id")
    tasks      = body.get("tasks", [])
    manager_email = body.get("manager_email", "")

    # Get manager employee id if exists
    cur.execute("SELECT id FROM employees WHERE email = %s", (manager_email,))
    mgr = cur.fetchone()
    checker_default = mgr["id"] if mgr else None

    inserted = []
    for t in tasks:
        # Resolve employee IDs by name
        def resolve(name):
            if not name: return None
            cur.execute("SELECT id FROM employees WHERE name ILIKE %s AND project_id = %s", (name, project_id))
            row = cur.fetchone()
            return row["id"] if row else None

        assignee_id  = resolve(t.get("assignee"))
        companion_id = resolve(t.get("companion"))
        guide_id     = resolve(t.get("guide"))
        checker_id   = resolve(t.get("checker")) or checker_default

        # Snapshot of assignee's current tasks at time of assignment
        snapshot = []
        if assignee_id:
            cur.execute("""
                SELECT title, priority, status FROM tasks
                WHERE assignee_id = %s AND status != 'done'
            """, (assignee_id,))
            snapshot = [dict(r) for r in cur.fetchall()]

        due_date     = t.get("due_date") if t.get("due_date") not in ("TBD", "", None) else None
        assigned_date = t.get("assigned_date") or "NOW()"

        cur.execute("""
            INSERT INTO tasks (
                title, project_id, meeting_id,
                assignee_id, companion_id, guide_id, checker_id,
                status, priority, assigned_date, due_date, total_days,
                notes, escalation_details, current_tasks_snapshot
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                'pending', %s,
                NOW(), %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            t.get("title"), project_id, meeting_id,
            assignee_id, companion_id, guide_id, checker_id,
            t.get("priority", "Medium"),
            due_date,
            t.get("total_days"),
            t.get("notes", ""),
            t.get("escalation_details", ""),
            json.dumps(snapshot),
        ))
        inserted.append(cur.fetchone()["id"])

    conn.commit()
    cur.close(); conn.close()
    return {"inserted": len(inserted), "task_ids": inserted}