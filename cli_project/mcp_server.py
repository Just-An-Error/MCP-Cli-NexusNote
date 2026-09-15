from core.db import get_connection, process_note, get_entity_relations, list_entities, merge_entities
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
load_dotenv()


mcp = FastMCP("NexusNote", log_level="ERROR")


@mcp.tool(
    name="add_note",
    description=(
        "Salva una nota in linguaggio naturale, estraendo automaticamente "
        "le entità (persone, progetti, idee, problemi) e le relazioni tra loro."
    ),
)
def add_note(
    text: str = Field(description="Il testo della nota da salvare."),
) -> dict:
    conn = get_connection()
    result = process_note(conn, text)
    conn.close()
    return result


@mcp.tool(
    name="query_entity",
    description=(
        "Recupera tutto quello che si sa su una entità (persona, progetto, "
        "idea o problema), incluse tutte le relazioni in cui è coinvolta."
    ),
)
def query_entity(
    name: str = Field(
        description="Il nome dell'entità da cercare (es. 'Marco')."),
) -> dict:
    conn = get_connection()
    relations = get_entity_relations(conn, name)
    conn.close()

    if not relations:
        return {"entity": name, "found": False, "relations": []}

    return {"entity": name, "found": True, "relations": relations}


@mcp.tool(
    name="list_entities",
    description=(
        "Elenca tutte le entità conosciute (persone, progetti, idee, problemi), "
        "opzionalmente filtrate per tipo."
    ),
)
def list_all_entities(
    type_filter: str = Field(
        default=None,
        description="Filtra per tipo: PERSONA, PROGETTO, IDEA o PROBLEMA. Lascia vuoto per vedere tutto.",
    ),
) -> dict:
    conn = get_connection()
    entities = list_entities(conn)
    conn.close()

    if type_filter:
        entities = [e for e in entities if e["type"] == type_filter.upper()]

    return {"entities": entities, "count": len(entities)}

@mcp.tool(
    name="merge_entities",
    description=(
        "Unisce due entità duplicate (stesso concetto, nomi diversi) in una sola. "
        "Usa questo quando noti due nomi che si riferiscono alla stessa cosa, "
        "es. 'Alpha' e 'progetto Alpha'."
    ),
)
def merge_entities_tool(
    keep_name: str = Field(description="Il nome da mantenere."),
    remove_name: str = Field(description="Il nome duplicato da rimuovere."),
    type_name: str = Field(description="Il tipo dell'entità: PERSONA, PROGETTO, IDEA o PROBLEMA."),
) -> dict:
    conn = get_connection()
    result = merge_entities(conn, keep_name, remove_name, type_name)
    conn.close()
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
