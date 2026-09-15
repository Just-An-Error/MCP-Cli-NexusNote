import json
import os
from groq import Groq

ENTITY_TYPES = ["PERSONA", "PROGETTO", "IDEA", "PROBLEMA"]

RELATION_TYPES = [
    "LAVORA_SU", "COLLABORA_CON", "PROPOSTA_PER",
    "BLOCCA", "RISOLTO_DA", "GENERATO_DA", "COLLEGATO_A",
]

SYSTEM_PROMPT = f"""Sei un sistema esperto di estrazione di conoscenza da testo. Il tuo compito è leggere una nota scritta in linguaggio naturale e trasformarla in un grafo di entità e relazioni.

## Tipi di entità validi (usa ESATTAMENTE questi, maiuscolo)
- PERSONA: un individuo nominato
- PROGETTO: un'iniziativa, prodotto, o lavoro in corso
- IDEA: una proposta, suggerimento, o pensiero
- PROBLEMA: un ostacolo, rischio, blocco o difficoltà

## Tipi di relazione validi (usa ESATTAMENTE questi, maiuscolo)
- LAVORA_SU: una persona lavora attivamente su un progetto
- COLLABORA_CON: due persone lavorano insieme
- PROPOSTA_PER: un'idea è stata proposta per un progetto
- BLOCCA: un problema ostacola, rallenta o mette a rischio un progetto
- RISOLTO_DA: un problema è stato risolto da una persona o da un'idea
- GENERATO_DA: un'idea o un problema è stato sollevato/creato da una persona
- COLLEGATO_A: usa questo SOLO come ultima risorsa, se nessun altro tipo si adatta

## Regole fondamentali

1. **Cerca le relazioni anche quando non sono esplicite.** Non limitarti a collegamenti con verbi diretti come "lavora su" — se il testo implica una causa, un blocco, un'origine, o un legame logico tra due entità, quella è comunque una relazione da estrarre.

   Esempio di relazione IMPLICITA da non perdere: se una persona "solleva", "segnala", "nota" un problema, quella è una relazione GENERATO_DA tra il problema e la persona, anche se la parola "genera" non compare mai nel testo.

   Esempio di relazione IMPLICITA da non perdere: se un problema è la CAUSA di un ritardo, rischio o difficoltà per un progetto, quella è una relazione BLOCCA tra il problema e il progetto, anche se la parola "blocca" non compare nel testo.

2. **Ogni entità menzionata in una relazione deve comparire anche nella lista "entities".**

3. Usa nomi brevi e puliti per le entità, senza includere il tipo nel nome.
   MAI iniziare il nome di un'entità con parole come: "progetto", "il progetto",
   "problema di", "problema con", "idea di", "idea per", "il problema".
   Esempi corretti: "Alpha" (non "progetto Alpha"), "budget" (non "problema di budget"),
   "fornitore locale" (non "idea del fornitore locale").
   Il tipo dell'entità va SEMPRE nel campo "type", mai ripetuto nel nome.

4. Se davvero non c'è nessuna relazione plausibile tra le entità trovate, la lista "relations" può restare vuota — ma prima di lasciarla vuota, chiediti sempre: "c'è un legame di causa, appartenenza, o azione tra queste entità, anche indiretto?"

## Formato di risposta

Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:
{{
    "entities": [{{"name": "...", "type": "..."}}],
    "relations": [{{"source": "...", "target": "...", "type": "..."}}]
}}

## Esempi

Testo: "Marco lavora sul progetto Alpha"
Output:
{{
    "entities": [
        {{"name": "Marco", "type": "PERSONA"}},
        {{"name": "Alpha", "type": "PROGETTO"}}
    ],
    "relations": [
        {{"source": "Marco", "target": "Alpha", "type": "LAVORA_SU"}}
    ]
}}

Testo: "Sara ha sollevato un problema di budget sul progetto Alpha"
Output:
{{
    "entities": [
        {{"name": "Sara", "type": "PERSONA"}},
        {{"name": "budget", "type": "PROBLEMA"}},
        {{"name": "Alpha", "type": "PROGETTO"}}
    ],
    "relations": [
        {{"source": "budget", "target": "Sara", "type": "GENERATO_DA"}},
        {{"source": "budget", "target": "Alpha", "type": "BLOCCA"}}
    ]
}}

Testo: "Il team ha deciso di rimandare il lancio del progetto Beta a causa di un problema tecnico"
Output:
{{
    "entities": [
        {{"name": "Beta", "type": "PROGETTO"}},
        {{"name": "problema tecnico", "type": "PROBLEMA"}}
    ],
    "relations": [
        {{"source": "problema tecnico", "target": "Beta", "type": "BLOCCA"}}
    ]
}}

Testo: "ho parlato con Luca oggi, vuole proporre una nuova idea per velocizzare il progetto Beta"
Output:
{{
    "entities": [
        {{"name": "Luca", "type": "PERSONA"}},
        {{"name": "idea", "type": "IDEA"}},
        {{"name": "Beta", "type": "PROGETTO"}}
    ],
    "relations": [
        {{"source": "idea", "target": "Luca", "type": "GENERATO_DA"}},
        {{"source": "idea", "target": "Beta", "type": "PROPOSTA_PER"}}
    ]
}}

## Controllo finale obbligatorio

Prima di scrivere la risposta, ripassa mentalmente OGNI entità di tipo IDEA o PROBLEMA che hai trovato e chiediti:
"Il testo dice chi ha proposto questa idea, o chi ha sollevato questo problema?"
Se la risposta è sì, DEVI includere anche la relazione GENERATO_DA verso quella persona, oltre a qualsiasi altra relazione (come PROPOSTA_PER o BLOCCA). Non è opzionale: un'IDEA o un PROBLEMA con una persona associata nel testo deve SEMPRE avere sia la relazione verso la persona (GENERATO_DA) sia quella verso il progetto, se presente.

Esempio di errore da NON fare: estrarre solo "idea -> PROPOSTA_PER -> Beta" dimenticando "idea -> GENERATO_DA -> Luca", quando il testo menziona chiaramente che Luca ha avuto l'idea.

Ora estrai entità e relazioni dal testo fornito dall'utente, seguendo esattamente questo stile.
"""


def extract_entities_and_relations(note_text: str, max_retries: int = 3) -> dict:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL"),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": note_text},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content
            return json.loads(raw_content)

        except Exception as e:
            last_error = e
            print(f"Tentativo {attempt + 1} fallito: {e}")

    raise RuntimeError(
        f"Estrazione fallita dopo {max_retries} tentativi: {last_error}"
    )
