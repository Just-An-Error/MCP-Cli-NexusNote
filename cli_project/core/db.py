import sqlite3
from pathlib import Path
from core.extractor import extract_entities_and_relations

DB_PATH = Path(__file__).parent / "NexusNote.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    # SQLite does not enforce foreign key constraints by default, so we need to enable it explicitly.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_or_create_entity(conn: sqlite3.Connection, name: str, type_name: str) -> int:
    # This variable in SQlite is used to execute SQL commands and fetch results. It acts as an intermediary between the database connection and the SQL statements.
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM entity_types WHERE name = ?", (type_name,)
    )
    type_row = cursor.fetchone()
    if type_row is None:
        raise ValueError(f"Questa entity type '{type_name}' non esiste.")
    type_id = type_row[0]

    cursor.execute(
        "SELECT id FROM entities WHERE name = ? AND type_id = ?",
        (name, type_id)
    )
    existing_entity_row = cursor.fetchone()
    if existing_entity_row:
        return existing_entity_row[0]

    cursor.execute(
        "INSERT INTO entities (name, type_id) VALUES (?, ?)", (name, type_id)
    )
    conn.commit()
    return cursor.lastrowid


def create_relation(
        conn: sqlite3.Connection,
        source_entity_id: int,
        target_entity_id: int,
        relation_type_name: str,
        note_id: int
) -> int:
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM relation_types WHERE name = ?", (relation_type_name,)
    )
    type_row = cursor.fetchone()
    if type_row is None:
        raise ValueError(
            f"Questa relation type '{relation_type_name}' non esiste.")
    relation_type_id = type_row[0]

    cursor.execute(
        "INSERT INTO relations (source_entity_id, target_entity_id, relation_type_id, note_id) VALUES (?, ?, ?, ?)",
        (source_entity_id, target_entity_id, relation_type_id, note_id)
    )
    conn.commit()
    return cursor.lastrowid


def save_note(conn: sqlite3.Connection, text: str) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notes (text) VALUES (?)", (text,)
    )
    conn.commit()
    return cursor.lastrowid


def get_entity_relations(conn: sqlite3.Connection, entity_name: str) -> list[dict]:
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            source.name AS source_name,
            relation_types.name AS relation_name,
            target.name AS target_name,
            notes.text AS note_text
        FROM relations
        JOIN entities AS source ON relations.source_entity_id = source.id
        JOIN entities AS target ON relations.target_entity_id = target.id
        JOIN relation_types ON relations.relation_type_id = relation_types.id
        JOIN notes ON relations.note_id = notes.id
        WHERE source.name = ? OR target.name = ?
        """,
        (entity_name, entity_name),
    )

    rows = cursor.fetchall()

    return [
        {
            "source": row[0],
            "relation": row[1],
            "target": row[2],
            "note": row[3],
        }
        for row in rows
    ]


def process_note(conn: sqlite3.Connection, text: str) -> dict:
    extracted = extract_entities_and_relations(text)

    note_id = save_note(conn, text)

    entity_name_to_id = {}
    for entity in extracted["entities"]:
        entity_id = get_or_create_entity(conn, entity["name"], entity["type"])
        entity_name_to_id[entity["name"]] = entity_id

    created_relations = []
    for relation in extracted["relations"]:
        source_id = entity_name_to_id.get(relation["source"])
        target_id = entity_name_to_id.get(relation["target"])
        if source_id is None or target_id is None:
            print(
                f"Attenzione: relazione ignorata {relation}. Una delle entità non è stata trovata.")
            continue

        relation_id = create_relation(
            conn, source_id, target_id, relation["type"], note_id
        )
        created_relations.append(relation_id)

        return {
            "note_id": note_id,
            "entities": list(entity_name_to_id.values()),
            "relations": created_relations
        }


def list_entities(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT entities.name, entity_types.name AS type
        FROM entities
        JOIN entity_types ON entities.type_id = entity_types.id
        ORDER BY entities.id
        """
    )

    rows = cursor.fetchall()

    return [{"name": row[0], "type": row[1]} for row in rows]

def merge_entities(conn: sqlite3.Connection, keep_name: str, remove_name: str, type_name: str) -> dict:
    cursor = conn.cursor()

    cursor.execute("Select id from entity_types where name = ?", (type_name,),)
    type_row = cursor.fetchone()
    if type_name is None:
        raise ValueError(f"Tipo Sconosciuto: {type_name}")
    type_id = type_row[0]

    cursor.execute("Select id from entities where name = ? and type_id = ?", (keep_name, type_id),)
    keep_row = cursor.fetchone()

    cursor.execute("select id from entities where name = ? and type_id = ?", (remove_name, type_id),)

    remove_row = cursor.fetchone()

    if keep_row is None or remove_row is None:
        raise ValueError("Una delle due entità non esiste con questo nome/tipo")

    keep_id = keep_row[0]
    remove_id = remove_row[0]

    if keep_id == remove_id:
        return {"merged": False, "reason": "Le due entità sono già la stessa"}

    cursor.execute(
        "UPDATE relations SET source_entity_id = ? WHERE source_entity_id = ?",
        (keep_id, remove_id),
    )
    cursor.execute(
        "UPDATE relations SET target_entity_id = ? WHERE target_entity_id = ?",
        (keep_id, remove_id),
    )

    cursor.execute(
        "Delete from entities where id = ?", (remove_id,)
    )

    conn.commit()

    return {"merged": True, "kept_id": keep_id, "removed_id": remove_id}