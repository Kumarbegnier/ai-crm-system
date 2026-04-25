import json
import os
import re
import hashlib
from datetime import datetime, timedelta
from .db import get_connection


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Normalize HCP name for deduplication: lowercase, remove titles, sort words."""
    name = name.lower().strip()
    # Remove common titles
    name = re.sub(r'\b(dr\.?|doctor|prof\.?|professor|mr\.?|mrs\.?|ms\.?|miss)\b', '', name)
    # Keep only letters and spaces
    name = re.sub(r'[^a-z\s]', '', name)
    # Sort words alphabetically for canonical form
    words = sorted(name.split())
    return ' '.join(words)


# ---------------------------------------------------------------------------
# Users CRUD
# ---------------------------------------------------------------------------

VALID_ROLES = ("sales_rep", "manager", "admin")


def _hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 with random salt. Returns 'salt$hash' string."""
    salt = hashlib.sha256(os.urandom(32)).hexdigest()
    h    = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return f"{salt}${h}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored 'salt$hash' string."""
    try:
        salt, h = stored.split("$", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
        return hashlib.compare_digest(candidate, h)
    except Exception:
        return False


def create_user(data: dict) -> int:
    """Create a new user. Hashes password if provided. Returns user id."""
    now = datetime.utcnow().isoformat()
    password_hash = _hash_password(data["password"]) if data.get("password") else None
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO users
               (name, email, phone, role, designation, region, city,
                password_hash, is_active, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,1,?,?) RETURNING id""",
            (
                data["name"], data["email"],
                data.get("phone"), data.get("role", "sales_rep"),
                data.get("designation"), data.get("region"), data.get("city"),
                password_hash, now, now,
            )
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id


def get_user_by_id(user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, phone, role, designation, region, city,"
            " is_active, total_interactions_logged, last_active_at, created_at, updated_at"
            " FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    """Returns full row including password_hash — for auth only."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
        return dict(row) if row else None


def get_all_users(role: str | None = None, region: str | None = None) -> list:
    with get_connection() as conn:
        query = (
            "SELECT id, name, email, phone, role, designation, region, city,"
            " is_active, total_interactions_logged, last_active_at FROM users"
        )
        params: list = []
        filters = []
        if role:
            filters.append("role = ? COLLATE NOCASE")
            params.append(role)
        if region:
            filters.append("region = ? COLLATE NOCASE")
            params.append(region)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY name"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def update_user(user_id: int, data: dict) -> bool:
    allowed = {
        "name", "phone", "role", "designation",
        "region", "city", "is_active",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return False
    now = datetime.utcnow().isoformat()
    updates["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            (*updates.values(), user_id)
        )
        conn.commit()
        return cur.rowcount > 0


def verify_user_password(email: str, password: str) -> dict | None:
    """Return user dict (without password_hash) if credentials are valid."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
        if not row:
            return None
        user = dict(row)
        if user.get("password_hash") and not _verify_password(password, user["password_hash"]):
            return None
        if not user.get("is_active", 1):
            return None
        # Update last_active_at in the same connection — no second transaction
        conn.execute(
            "UPDATE users SET last_active_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user["id"])
        )
        conn.commit()
    user.pop("password_hash", None)
    return user


def deactivate_user(user_id: int) -> bool:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
            (now, user_id)
        )
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# HCP CRUD
# ---------------------------------------------------------------------------

def upsert_hcp(data: dict) -> int:
    """Insert or update an HCP by name. Returns the hcp id."""
    fields = [
        "specialty", "sub_specialty", "qualification",
        "organization", "department",
        "phone", "email",
        "city", "state", "country",
        "priority", "status", "created_by",
    ]
    with get_connection() as conn:
        # Check if exists
        row = conn.execute(
            "SELECT id FROM hcps WHERE name = ? COLLATE NOCASE",
            (data["name"],)
        ).fetchone()

        now = datetime.utcnow().isoformat()
        norm_name = normalize_name(data["name"])

        if row:
            hcp_id = row[0]
            updates = {f: data[f] for f in fields if f in data}
            updates["updated_at"] = now
            updates["normalized_name"] = norm_name
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE hcps SET {set_clause} WHERE id = ?",
                (*updates.values(), hcp_id)
            )
        else:
            cols = ["name", "normalized_name"] + [f for f in fields if f in data] + ["created_at", "updated_at"]
            vals = [data["name"], norm_name] + [data[f] for f in fields if f in data] + [now, now]
            placeholders = ", ".join("?" * len(cols))
            conn.execute(
                f"INSERT INTO hcps ({', '.join(cols)}) VALUES ({placeholders})",
                vals
            )
            hcp_id = conn.execute(
                "SELECT id FROM hcps WHERE name = ? COLLATE NOCASE", (data["name"],)
            ).fetchone()[0]

        conn.commit()
        return hcp_id


def get_hcp_profile(name: str) -> dict | None:
    """Return full HCP profile by name."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hcps WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        return dict(row) if row else None


def get_all_hcp() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, name, specialty, organization, city, state,
                      priority, status, engagement_score,
                      total_interactions, last_interaction_date
               FROM hcps
               ORDER BY name"""
        ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

def create_appointment(hcp_id: int, date: str, time: str, notes: str | None = None) -> int:
    """Create an appointment. Raises IntegrityError if conflict."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO appointments (hcp_id, date, time, status, notes, created_at, updated_at)
               VALUES (?, ?, ?, 'scheduled', ?, ?, ?) RETURNING id""",
            (hcp_id, date, time, notes, now, now)
        )
        appointment_id = cur.fetchone()[0]
        conn.commit()
        return appointment_id


def is_available(hcp_id: int, date: str, time: str) -> bool:
    """Check if an HCP has no conflicting appointment at date+time."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM appointments WHERE hcp_id = ? AND date = ? AND time = ? AND status = 'scheduled'",
            (hcp_id, date, time)
        ).fetchone()
        return row is None


def get_appointments(hcp_name: str | None = None, date: str | None = None, status: str | None = None) -> list:
    """List appointments with optional filters."""
    with get_connection() as conn:
        query = """SELECT a.id, h.name AS hcp_name, a.date, a.time, a.status, a.notes, a.created_at
                   FROM appointments a
                   JOIN hcps h ON a.hcp_id = h.id"""
        filters = []
        params = []
        if hcp_name:
            filters.append("h.name = ? COLLATE NOCASE")
            params.append(hcp_name)
        if date:
            filters.append("a.date = ?")
            params.append(date)
        if status:
            filters.append("a.status = ?")
            params.append(status)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY a.date DESC, a.time ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def suggest_alternatives(hcp_id: int, date: str, time: str) -> list:
    """Suggest alternative slots near the requested time on the same date."""
    with get_connection() as conn:
        # Get all scheduled times for this HCP on this date
        rows = conn.execute(
            "SELECT time FROM appointments WHERE hcp_id = ? AND date = ? AND status = 'scheduled'",
            (hcp_id, date)
        ).fetchall()
        taken = {r[0] for r in rows}

        # Generate candidate slots every 30 min from 09:00 to 17:00
        candidates = []
        hour, minute = 9, 0
        while hour < 17:
            slot = f"{hour:02d}:{minute:02d}"
            if slot not in taken and slot != time:
                candidates.append(slot)
            minute += 30
            if minute >= 60:
                minute = 0
                hour += 1
        return candidates[:3]


def get_appointment_by_id(appointment_id: int) -> dict | None:
    """Fetch a single appointment by ID."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT a.id, h.name AS hcp_name, a.date, a.time, a.status, a.notes, a.created_at
               FROM appointments a
               JOIN hcps h ON a.hcp_id = h.id
               WHERE a.id = ?""",
            (appointment_id,)
        ).fetchone()
        return dict(row) if row else None


def cancel_appointment(appointment_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE appointments SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), appointment_id)
        )
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

def insert_interaction(
    hcp_name: str,
    notes: str,
    interaction_type: str = "call",
    interaction_channel: str | None = None,
    interaction_date: str | None = None,
    raw_input: str | None = None,
    ai_summary: str | None = None,
    ai_entities: dict | None = None,
    sentiment: str | None = None,
    product_discussed: str | None = None,
    outcome: str | None = None,
    follow_up_required: bool = False,
    follow_up_date: str | None = None,
    user_id: int | None = None,
    metadata: list[dict] | None = None,
) -> int:
    """
    Upsert HCP, insert rich interaction, auto-store ai_entities as metadata
    rows, and update CRM intelligence fields — all in a single transaction.
    """
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO hcps (name) VALUES (?)", (hcp_name,))
        row = conn.execute(
            "SELECT id, total_interactions FROM hcps WHERE name = ? COLLATE NOCASE",
            (hcp_name,)
        ).fetchone()
        hcp_id = row["id"]
        total  = (row["total_interactions"] or 0) + 1
        now    = datetime.utcnow().isoformat()

        cur = conn.execute(
            """INSERT INTO interactions (
                hcp_id, user_id,
                interaction_type, interaction_channel, interaction_date,
                notes, raw_input, ai_summary, ai_entities,
                sentiment, product_discussed, outcome,
                follow_up_required, follow_up_date,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (
                hcp_id, user_id,
                interaction_type, interaction_channel, interaction_date or now,
                notes, raw_input, ai_summary,
                json.dumps(ai_entities) if ai_entities else None,
                sentiment, product_discussed, outcome,
                1 if follow_up_required else 0, follow_up_date,
                now, now,
            )
        )
        interaction_id = cur.fetchone()[0]

        # Auto-expand ai_entities dict into metadata rows (source=llm)
        if ai_entities and isinstance(ai_entities, dict):
            _insert_metadata_rows(conn, interaction_id, ai_entities, source="llm", now=now)

        # Explicit metadata rows passed by caller (source=user or system)
        if metadata:
            for m in metadata:
                _insert_metadata_rows(
                    conn, interaction_id,
                    {m["key"]: m.get("value")},
                    source=m.get("source", "user"),
                    value_type=m.get("value_type", "string"),
                    confidence_score=m.get("confidence_score"),
                    now=now,
                )

        score = min(round(total * 10, 1), 100.0)
        conn.execute(
            """UPDATE hcps
               SET total_interactions    = ?,
                   last_interaction_date = ?,
                   engagement_score      = ?,
                   updated_at            = ?
               WHERE id = ?""",
            (total, now, score, now, hcp_id)
        )
        # Inline user metrics update — same transaction, no second connection
        if user_id:
            conn.execute(
                """UPDATE users
                   SET total_interactions_logged = total_interactions_logged + 1,
                       last_active_at = ?,
                       updated_at     = ?
                   WHERE id = ?""",
                (now, now, user_id)
            )
        conn.commit()
        return interaction_id


def _insert_metadata_rows(
    conn,
    interaction_id: int,
    data: dict,
    source: str = "llm",
    value_type: str = "string",
    confidence_score: float | None = None,
    now: str | None = None,
):
    """Insert one metadata row per key-value pair."""
    ts = now or datetime.utcnow().isoformat()
    for key, value in data.items():
        # Infer value_type from Python type
        if isinstance(value, bool):
            vtype, vstr = "boolean", str(value).lower()
        elif isinstance(value, (int, float)):
            vtype, vstr = "number", str(value)
        elif isinstance(value, dict):
            vtype, vstr = "json", json.dumps(value)
        elif isinstance(value, list):
            vtype, vstr = "json", json.dumps(value)
        else:
            vtype, vstr = value_type, str(value) if value is not None else None
        conn.execute(
            """INSERT INTO interaction_metadata
               (interaction_id, key, value, value_type, source, confidence_score, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (interaction_id, key, vstr, vtype, source, confidence_score, ts)
        )


def get_interactions_by_hcp(name: str) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT i.id, h.name, i.interaction_type, i.interaction_channel,
                      i.interaction_date, i.notes, i.ai_summary, i.ai_entities,
                      i.sentiment, i.product_discussed, i.outcome,
                      i.follow_up_required, i.follow_up_date, i.created_at
               FROM interactions i
               JOIN hcps h ON i.hcp_id = h.id
               WHERE h.name = ? COLLATE NOCASE
               ORDER BY i.interaction_date DESC""",
            (name,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("ai_entities"):
                try:
                    d["ai_entities"] = json.loads(d["ai_entities"])
                except (ValueError, TypeError):
                    pass
            result.append(d)
        return result


def get_pending_followups() -> list:
    """Return all interactions with follow_up_required=1, with overdue flag."""
    today = datetime.utcnow().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT i.id, h.name AS hcp_name, i.interaction_type,
                      i.notes, i.follow_up_date, i.outcome, i.product_discussed,
                      CASE
                        WHEN i.follow_up_date IS NOT NULL AND i.follow_up_date < ? THEN 1
                        ELSE 0
                      END AS is_overdue
               FROM interactions i
               JOIN hcps h ON i.hcp_id = h.id
               WHERE i.follow_up_required = 1
               ORDER BY is_overdue DESC,
                        CASE WHEN i.follow_up_date IS NULL THEN 1 ELSE 0 END,
                        i.follow_up_date ASC""",
            (today,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_daily_summary() -> dict:
    """Aggregate today's activity: visits, interactions, top HCP, segment insight."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_end   = datetime.utcnow().isoformat()
    with get_connection() as conn:
        # Interactions logged today
        total_interactions = conn.execute(
            "SELECT COUNT(*) FROM interactions WHERE interaction_date >= ? AND interaction_date <= ?",
            (today_start, today_end)
        ).fetchone()[0]

        # Unique HCPs visited today
        unique_hcps = conn.execute(
            """SELECT COUNT(DISTINCT hcp_id) FROM interactions
               WHERE interaction_date >= ? AND interaction_date <= ?""",
            (today_start, today_end)
        ).fetchone()[0]

        # Follow-ups scheduled today
        followups_today = conn.execute(
            """SELECT COUNT(*) FROM interactions
               WHERE follow_up_required = 1
                 AND follow_up_date >= ? AND follow_up_date <= ?""",
            (today_start, today_end)
        ).fetchone()[0]

        # Top HCP today by interaction count
        top_row = conn.execute(
            """SELECT h.name, h.specialty, COUNT(*) AS cnt
               FROM interactions i
               JOIN hcps h ON i.hcp_id = h.id
               WHERE i.interaction_date >= ? AND i.interaction_date <= ?
               GROUP BY h.id
               ORDER BY cnt DESC LIMIT 1""",
            (today_start, today_end)
        ).fetchone()
        top_hcp = dict(top_row) if top_row else None

        # Top specialty segment today
        segment_row = conn.execute(
            """SELECT h.specialty, COUNT(*) AS cnt
               FROM interactions i
               JOIN hcps h ON i.hcp_id = h.id
               WHERE i.interaction_date >= ? AND i.interaction_date <= ?
                 AND h.specialty IS NOT NULL
               GROUP BY h.specialty
               ORDER BY cnt DESC LIMIT 1""",
            (today_start, today_end)
        ).fetchone()
        top_segment = dict(segment_row) if segment_row else None

        # Overdue follow-ups
        overdue = conn.execute(
            """SELECT COUNT(*) FROM interactions
               WHERE follow_up_required = 1
                 AND follow_up_date IS NOT NULL
                 AND follow_up_date < ?""",
            (today_start,)
        ).fetchone()[0]

    return {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "total_interactions": total_interactions,
        "unique_hcps_visited": unique_hcps,
        "followups_scheduled_today": followups_today,
        "overdue_followups": overdue,
        "top_hcp": top_hcp,
        "top_segment": top_segment,
    }


def delete_interaction(interaction_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM interactions WHERE id = ?", (interaction_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def get_metadata_by_interaction(interaction_id: int) -> list:
    """Return all metadata rows for a given interaction."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, key, value, value_type, source, confidence_score, created_at
               FROM interaction_metadata
               WHERE interaction_id = ?
               ORDER BY source, key""",
            (interaction_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_metadata_by_key(key: str, source: str | None = None) -> list:
    """Search all metadata rows by key, optionally filtered by source."""
    with get_connection() as conn:
        if source:
            rows = conn.execute(
                """SELECT m.id, m.interaction_id, h.name AS hcp_name,
                          m.key, m.value, m.value_type, m.source,
                          m.confidence_score, m.created_at
                   FROM interaction_metadata m
                   JOIN interactions i ON m.interaction_id = i.id
                   JOIN hcps h ON i.hcp_id = h.id
                   WHERE m.key = ? AND m.source = ?
                   ORDER BY m.created_at DESC""",
                (key, source)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT m.id, m.interaction_id, h.name AS hcp_name,
                          m.key, m.value, m.value_type, m.source,
                          m.confidence_score, m.created_at
                   FROM interaction_metadata m
                   JOIN interactions i ON m.interaction_id = i.id
                   JOIN hcps h ON i.hcp_id = h.id
                   WHERE m.key = ?
                   ORDER BY m.created_at DESC""",
                (key,)
            ).fetchall()
        return [dict(row) for row in rows]


def upsert_metadata(
    interaction_id: int,
    key: str,
    value: str,
    value_type: str = "string",
    source: str = "user",
    confidence_score: float | None = None,
) -> int:
    """Insert or replace a single metadata key for an interaction."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM interaction_metadata WHERE interaction_id=? AND key=? AND source=?",
            (interaction_id, key, source)
        )
        cur = conn.execute(
            """INSERT INTO interaction_metadata
               (interaction_id, key, value, value_type, source, confidence_score, created_at)
               VALUES (?,?,?,?,?,?,?) RETURNING id""",
            (interaction_id, key, value, value_type, source, confidence_score, now)
        )
        metadata_id = cur.fetchone()[0]
        conn.commit()
        return metadata_id


def delete_metadata(metadata_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM interaction_metadata WHERE id=?", (metadata_id,)
        )
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# CRM Intelligence Queries
# ---------------------------------------------------------------------------

def get_inactive_hcps(days: int = 30) -> list:
    """HCPs with no interaction in the last `days` days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT h.id, h.name, h.specialty, h.organization,
                      h.priority, h.engagement_score,
                      MAX(i.interaction_date) AS last_interaction
               FROM hcps h
               LEFT JOIN interactions i ON i.hcp_id = h.id
               WHERE h.status = 'active'
               GROUP BY h.id
               HAVING last_interaction IS NULL OR last_interaction < ?
               ORDER BY last_interaction ASC""",
            (cutoff,)
        ).fetchall()
        return [dict(row) for row in rows]


def recommend_hcps(limit: int = 5) -> list:
    """AI-driven HCP recommendation using weighted scoring:
    score = (1/recency)*0.6 + frequency*0.4
    Higher score = more urgent to visit.
    """
    today = datetime.utcnow().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT
                 h.id, h.name, h.specialty, h.organization, h.city,
                 h.priority, h.total_interactions, h.last_interaction_date,
                 -- Most recent product discussed
                 (
                   SELECT i2.product_discussed
                   FROM interactions i2
                   WHERE i2.hcp_id = h.id AND i2.product_discussed IS NOT NULL
                   ORDER BY i2.interaction_date DESC LIMIT 1
                 ) AS last_product,
                 -- Days since last interaction
                 COALESCE(CAST(
                   (julianday(?) - julianday(h.last_interaction_date))
                 AS INTEGER), 999) AS days_since_visit,
                 -- Overdue follow-up flag
                 (
                   SELECT COUNT(*)
                   FROM interactions i3
                   WHERE i3.hcp_id = h.id
                     AND i3.follow_up_required = 1
                     AND (i3.follow_up_date IS NULL OR i3.follow_up_date < ?)
                 ) AS overdue_followups
               FROM hcps h
               WHERE h.status = 'active'
               ORDER BY h.id""",
            (today, today)
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            days = d.get("days_since_visit") or 999
            freq = d.get("total_interactions") or 0

            # AI scoring: higher score = higher priority to visit
            recency_score = (1.0 / max(days, 1)) * 0.6
            frequency_score = min(freq / 10.0, 1.0) * 0.4
            ai_score = round((recency_score + frequency_score) * 100, 2)

            d["ai_score"] = ai_score
            d["recency_component"] = round(recency_score * 100, 2)
            d["frequency_component"] = round(frequency_score * 100, 2)
            results.append(d)

        # Sort by AI score descending, then overdue follow-ups, then days since visit
        results.sort(key=lambda x: (-x["ai_score"], -x["overdue_followups"], x["days_since_visit"]))
        return results[:limit]


def get_hcps_by_priority(priority: str) -> list:
    """Filter HCPs by priority: high / medium / low."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, name, specialty, organization, city,
                      engagement_score, total_interactions, last_interaction_date
               FROM hcps
               WHERE priority = ? COLLATE NOCASE AND status = 'active'
               ORDER BY engagement_score DESC""",
            (priority,)
        ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Tags CRUD
# ---------------------------------------------------------------------------

def upsert_tag(name: str, category: str | None = None, description: str | None = None) -> int:
    """Insert tag if not exists (case-insensitive), return its id."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, category, description) VALUES (?, ?, ?)",
            (name, category, description)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        return row[0]


def get_all_tags(category: str | None = None) -> list:
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM tags WHERE category = ? COLLATE NOCASE ORDER BY name",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
        return [dict(row) for row in rows]


def get_tag_by_name(name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tags WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        return dict(row) if row else None


def delete_tag(tag_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# HCP ↔ Tags mapping
# ---------------------------------------------------------------------------

def assign_tag_to_hcp(
    hcp_id: int,
    tag_id: int,
    confidence_score: float | None = None,
    source: str = "llm",
) -> bool:
    """Assign a tag to an HCP. Returns True if inserted, False if already exists."""
    with get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO hcp_tags (hcp_id, tag_id, confidence_score, source)
                   VALUES (?, ?, ?, ?)""",
                (hcp_id, tag_id, confidence_score, source)
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False


def remove_tag_from_hcp(hcp_id: int, tag_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM hcp_tags WHERE hcp_id = ? AND tag_id = ?", (hcp_id, tag_id)
        )
        conn.commit()
        return cur.rowcount > 0


def get_hcp_tags(hcp_name: str) -> list:
    """Return all tags assigned to an HCP with confidence and source."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.id, t.name, t.category, t.description,
                      ht.confidence_score, ht.source, ht.created_at
               FROM hcp_tags ht
               JOIN hcps h ON ht.hcp_id = h.id
               JOIN tags t ON ht.tag_id = t.id
               WHERE h.name = ? COLLATE NOCASE
               ORDER BY t.category, t.name""",
            (hcp_name,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_hcps_by_tag(tag_name: str) -> list:
    """Return all HCPs tagged with a given tag name."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT h.id, h.name, h.specialty, h.organization, h.city,
                      h.priority, h.status, h.engagement_score,
                      ht.confidence_score, ht.source, ht.created_at
               FROM hcps h
               JOIN hcp_tags ht ON h.id = ht.hcp_id
               JOIN tags t ON ht.tag_id = t.id
               WHERE t.name = ? COLLATE NOCASE AND h.status = 'active'
               ORDER BY h.name""",
            (tag_name,)
        ).fetchall()
        return [dict(row) for row in rows]
