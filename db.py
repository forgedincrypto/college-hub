import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "college_hub.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        name TEXT DEFAULT '',
        high_school TEXT DEFAULT '',
        grad_year INTEGER,
        sat_score INTEGER,
        act_score INTEGER,
        major_interests TEXT DEFAULT '',
        extracurriculars TEXT DEFAULT '',
        location_pref TEXT DEFAULT '',
        size_pref TEXT DEFAULT '',
        budget TEXT DEFAULT '',
        setting_pref TEXT DEFAULT '',
        important_factors TEXT DEFAULT '',
        additional_notes TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        grade TEXT NOT NULL,
        year TEXT NOT NULL,
        course_type TEXT DEFAULT 'Regular',
        credits REAL DEFAULT 1.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT DEFAULT 'New Conversation',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS college_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        tier TEXT NOT NULL CHECK (tier IN ('reach', 'match', 'safety')),
        reasoning TEXT DEFAULT '',
        fit_score INTEGER DEFAULT 0,
        location TEXT DEFAULT '',
        size TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        college_name TEXT NOT NULL,
        status TEXT DEFAULT 'Researching',
        deadline TEXT,
        app_type TEXT DEFAULT 'Regular Decision',
        essay_status TEXT DEFAULT 'Not Started',
        lor_count INTEGER DEFAULT 0,
        transcript_sent INTEGER DEFAULT 0,
        test_scores_sent INTEGER DEFAULT 0,
        financial_aid INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    INSERT OR IGNORE INTO profile (id) VALUES (1);
    """)
    conn.commit()
    conn.close()


# ── Profile helpers ──────────────────────────────────────────────

def get_profile():
    conn = get_db()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def update_profile(**kwargs):
    conn = get_db()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values())
    conn.execute(f"UPDATE profile SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = 1", vals)
    conn.commit()
    conn.close()


# ── Course helpers ───────────────────────────────────────────────

GRADE_POINTS = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}

WEIGHT_BONUS = {"AP": 1.0, "IB": 1.0, "Honors": 0.5, "Dual Enrollment": 0.5, "Regular": 0.0}


def get_courses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM courses ORDER BY year, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_course(name, grade, year, course_type="Regular", credits=1.0):
    conn = get_db()
    conn.execute(
        "INSERT INTO courses (name, grade, year, course_type, credits) VALUES (?, ?, ?, ?, ?)",
        (name, grade, year, course_type, credits),
    )
    conn.commit()
    conn.close()


def delete_course(course_id):
    conn = get_db()
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.commit()
    conn.close()


def calc_gpa(courses):
    if not courses:
        return {"unweighted": 0.0, "weighted": 0.0}
    total_credits = 0
    uw_points = 0
    w_points = 0
    for c in courses:
        gp = GRADE_POINTS.get(c["grade"], 0.0)
        bonus = WEIGHT_BONUS.get(c["course_type"], 0.0)
        cr = c["credits"]
        uw_points += gp * cr
        w_points += (gp + bonus) * cr
        total_credits += cr
    if total_credits == 0:
        return {"unweighted": 0.0, "weighted": 0.0}
    return {
        "unweighted": round(uw_points / total_credits, 3),
        "weighted": round(w_points / total_credits, 3),
    }


# ── Conversation / message helpers ───────────────────────────────

def get_conversations():
    conn = get_db()
    rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_conversation(title="New Conversation"):
    conn = get_db()
    cur = conn.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def get_messages(conversation_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conversation_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_message(conversation_id, role, content):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, role, content),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,),
    )
    conn.commit()
    conn.close()


def update_conversation_title(conversation_id, title):
    conn = get_db()
    conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
    conn.commit()
    conn.close()


def delete_conversation(conversation_id):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()


# ── College match helpers ────────────────────────────────────────

def get_college_matches():
    conn = get_db()
    rows = conn.execute("SELECT * FROM college_matches ORDER BY tier, fit_score DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_college_matches(matches):
    """Replace all matches with a new list of dicts."""
    conn = get_db()
    conn.execute("DELETE FROM college_matches")
    for m in matches:
        conn.execute(
            "INSERT INTO college_matches (name, tier, reasoning, fit_score, location, size) VALUES (?, ?, ?, ?, ?, ?)",
            (m["name"], m["tier"], m.get("reasoning", ""), m.get("fit_score", 0),
             m.get("location", ""), m.get("size", "")),
        )
    conn.commit()
    conn.close()


def delete_all_matches():
    conn = get_db()
    conn.execute("DELETE FROM college_matches")
    conn.commit()
    conn.close()


# ── Application tracker helpers ──────────────────────────────────

def get_applications():
    conn = get_db()
    rows = conn.execute("SELECT * FROM applications ORDER BY deadline, college_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_application(college_name, deadline=None, app_type="Regular Decision"):
    conn = get_db()
    conn.execute(
        "INSERT INTO applications (college_name, deadline, app_type) VALUES (?, ?, ?)",
        (college_name, deadline, app_type),
    )
    conn.commit()
    conn.close()


def update_application(app_id, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values())
    conn.execute(
        f"UPDATE applications SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        vals + [app_id],
    )
    conn.commit()
    conn.close()


def delete_application(app_id):
    conn = get_db()
    conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()


# ── Stats for dashboard ─────────────────────────────────────────

def get_dashboard_stats():
    profile = get_profile()
    courses = get_courses()
    gpa = calc_gpa(courses)
    matches = get_college_matches()
    apps = get_applications()

    # Profile completion
    profile_fields = [
        "name", "high_school", "grad_year", "major_interests",
        "extracurriculars", "location_pref", "size_pref", "budget",
    ]
    filled = sum(1 for f in profile_fields if profile.get(f))
    profile_pct = int(filled / len(profile_fields) * 100)

    # Upcoming deadlines (next 3)
    upcoming = [a for a in apps if a.get("deadline")]
    upcoming.sort(key=lambda a: a["deadline"])
    upcoming = upcoming[:3]

    return {
        "gpa": gpa,
        "sat_score": profile.get("sat_score"),
        "act_score": profile.get("act_score"),
        "course_count": len(courses),
        "profile_pct": profile_pct,
        "match_count": len(matches),
        "reach_count": sum(1 for m in matches if m["tier"] == "reach"),
        "match_tier_count": sum(1 for m in matches if m["tier"] == "match"),
        "safety_count": sum(1 for m in matches if m["tier"] == "safety"),
        "app_count": len(apps),
        "upcoming_deadlines": upcoming,
    }


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
