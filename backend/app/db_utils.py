from .db import get_connection


def get_or_create_hcp(name):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM hcp WHERE name=%s", (name,))
    res = cur.fetchone()

    if res:
        hcp_id = res[0]
    else:
        cur.execute(
            "INSERT INTO hcp (name) VALUES (%s) RETURNING id",
            (name,)
        )
        hcp_id = cur.fetchone()[0]
        conn.commit()

    cur.close()
    conn.close()
    return hcp_id


def insert_interaction(hcp_name, notes):
    conn = get_connection()
    cur = conn.cursor()

    hcp_id = get_or_create_hcp(hcp_name)

    cur.execute(
        "INSERT INTO interactions (hcp_id, notes) VALUES (%s, %s)",
        (hcp_id, notes)
    )

    conn.commit()
    cur.close()
    conn.close()


def get_all_hcp():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM hcp")
    data = cur.fetchall()

    cur.close()
    conn.close()
    return data


def get_interactions_by_hcp(name):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT i.id, h.name, i.notes, i.created_at
        FROM interactions i
        JOIN hcp h ON i.hcp_id = h.id
        WHERE h.name = %s
    """, (name,))

    data = cur.fetchall()

    cur.close()
    conn.close()
    return data


def delete_interaction(interaction_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM interactions WHERE id=%s", (interaction_id,))
    conn.commit()

    cur.close()
    conn.close()

