# NexusNote

NexusNote è una CLI per salvare e interrogare appunti in linguaggio naturale. L'idea è simile a una knowledge base personale: l'utente scrive una nota, il modello individua le entità e i collegamenti importanti, e il progetto li conserva in SQLite per poterli recuperare in seguito.

Il progetto usa ancora MCP, ma solo come canale interno tra la chat e il servizio che gestisce le note. `mcp_client.py` e `mcp_server.py` non sono codice abbandonato: sono necessari all'avvio dell'applicazione e alla chiamata degli strumenti `add_note`, `query_entity`, `list_entities` e `merge_entities`.

## Flusso dell'applicazione

1. `main.py` carica le variabili d'ambiente e crea il servizio Groq.
2. `main.py` avvia `mcp_server.py` come processo MCP tramite stdio.
3. `mcp_client.py` apre la sessione con quel processo e rende disponibili gli strumenti MCP.
4. `core/cli.py` legge una domanda dalla console.
5. `core/chat.py` invia la conversazione e l'elenco degli strumenti a Groq.
6. Se il modello decide di usare uno strumento, `core/tools.py` individua il client corretto, esegue la chiamata e restituisce il risultato al modello.
7. `mcp_server.py` delega l'operazione a `core/db.py`.
8. `core/db.py` salva o interroga `core/NexusNote.db`; durante il salvataggio usa `core/extractor.py` per estrarre il grafo dalla nota.

In forma compatta:

```text
Utente
  -> core/cli.py
  -> core/chat.py
  -> core/claude.py (Groq)
  -> core/tools.py
  -> mcp_client.py
  -> mcp_server.py
  -> core/db.py
  -> core/extractor.py e SQLite
```

## File principali

### `main.py`

È l'entry point dell'applicazione. Non contiene la logica delle note: coordina soltanto l'avvio dei servizi.

Responsabilità:

- caricare `.env` con `python-dotenv`;
- leggere `CLAUDE_MODEL`, `GROQ_API_KEY` e `USE_UV`;
- verificare che il modello e la chiave API siano presenti;
- creare `core.claude.Claude`;
- avviare il server MCP usando `uv run mcp_server.py` quando `USE_UV=1`, oppure `python mcp_server.py` negli altri casi;
- creare una sessione `MCPClient` e registrarla come client degli strumenti delle note;
- collegare la sessione MCP a `Chat` e avviare `CliApp`.

Il file configura anche l'event loop compatibile con Windows. Non accetta più script MCP esterni da riga di comando: quella era una modalità generica del vecchio progetto e non è necessaria per NexusNote.

### `mcp_client.py`

Contiene la classe `MCPClient`, cioè l'adapter client-side per il protocollo MCP su stdio.

Responsabilità:

- costruire i parametri del processo server;
- aprire il trasporto stdio;
- inizializzare `ClientSession`;
- esporre `list_tools()` per scoprire gli strumenti disponibili;
- esporre `call_tool()` per invocare uno strumento con i suoi argomenti;
- chiudere correttamente trasporto e sessione tramite `AsyncExitStack`;
- funzionare come async context manager con `async with`.

Il client non salva dati e non conosce SQLite. Si limita a trasportare richieste e risposte tra la chat e `mcp_server.py`. Sono state rimosse le vecchie operazioni per prompt e resource MCP, perché il server attuale non ne espone nessuna.

### `mcp_server.py`

È il server MCP dell'applicazione. Registra gli strumenti che il modello può usare per lavorare sulla knowledge base.

Gli strumenti sono:

- `add_note`: riceve testo naturale e lo passa a `process_note`;
- `query_entity`: cerca tutte le relazioni di un'entità;
- `list_entities`: elenca le entità, con filtro opzionale per tipo;
- `merge_entities`: unisce due nomi che rappresentano la stessa entità.

Ogni strumento apre una connessione al database, delega il lavoro a `core.db` e chiude la connessione. Il blocco `if __name__ == "__main__"` avvia il server con trasporto stdio, che è il trasporto usato da `MCPClient`.

### `core/__init__.py`

È volutamente vuoto. Serve a trattare `core` come package Python e non contiene stato o inizializzazione globale. Lasciarlo vuoto evita effetti collaterali quando gli altri moduli vengono importati.

### `core/cli.py`

Implementa l'interfaccia interattiva del terminale tramite `prompt_toolkit`.

`CliApp`:

- crea una sessione con storia in memoria;
- configura il prompt e i colori del terminale;
- legge input non vuoto in modo asincrono;
- passa ogni richiesta a `Chat.run()`;
- stampa la risposta finale;
- termina con `Ctrl+C`.

In precedenza conteneva autocompletamento per prompt MCP, risorse e documenti. Quelle API non erano implementate dal server NexusNote e i metodi di aggiornamento non venivano mai chiamati, quindi sono stati rimossi. La CLI ora riflette il flusso reale: domande libere in linguaggio naturale.

### `core/chat.py`

Coordina il ciclo conversazionale tra utente, modello e strumenti.

Il metodo `run()`:

1. aggiunge la domanda dell'utente alla cronologia;
2. chiede a `Claude` una risposta, includendo gli strumenti MCP disponibili;
3. salva nella cronologia il messaggio dell'assistente;
4. se il modello ha prodotto tool call, delega l'esecuzione a `ToolManager`;
5. aggiunge i risultati degli strumenti alla conversazione;
6. ripete il ciclo finché il modello produce testo senza nuove tool call;
7. restituisce il testo finale.

La cronologia resta nell'istanza `Chat`, quindi le richieste successive della stessa sessione possono usare il contesto precedente.

### `core/claude.py`

Contiene l'adapter verso l'SDK Groq. Il nome della classe `Claude` è storico e non descrive il provider attuale: il codice usa `groq.Groq`, non l'SDK Anthropic.

Responsabilità:

- creare il client Groq usando `GROQ_API_KEY`;
- convertire la lista di strumenti MCP nel formato tool calling richiesto da Groq;
- aggiungere un eventuale messaggio di sistema;
- inviare messaggi, temperatura e strumenti al modello;
- restituire il messaggio prodotto dal modello;
- convertire i risultati delle tool call in messaggi `tool` compatibili con la conversazione.

Il modulo non decide quali strumenti eseguire: riceve la risposta del modello e lascia a `core.tools` la gestione delle chiamate.

### `core/db.py`

È il livello di persistenza e di dominio della knowledge base. Usa SQLite senza introdurre un ORM.

`DB_PATH` punta a `core/NexusNote.db`, quindi il database viene mantenuto vicino al codice del dominio. `get_connection()` apre la connessione e abilita le foreign key di SQLite.

Funzioni principali:

- `get_or_create_entity`: trova o crea un'entità associata a un tipo;
- `create_relation`: trova il tipo di relazione e salva un collegamento tra due entità;
- `save_note`: salva il testo originale e restituisce l'id della nota;
- `get_entity_relations`: legge relazioni, nomi e testo delle note collegate a un'entità;
- `process_note`: usa `extractor` per ottenere entità e relazioni, salva la nota, crea le entità e collega i nodi;
- `list_entities`: restituisce l'elenco delle entità con il relativo tipo;
- `merge_entities`: sostituisce nei collegamenti l'entità duplicata con quella mantenuta e rimuove il duplicato.

Questo modulo contiene SQL e regole di persistenza, ma non contiene codice MCP e non interagisce direttamente con il terminale o con Groq.

### `core/extractor.py`

Trasforma una nota libera in una struttura JSON composta da `entities` e `relations` usando Groq.

Definisce i vocabolari ammessi:

- entità: `PERSONA`, `PROGETTO`, `IDEA`, `PROBLEMA`;
- relazioni: `LAVORA_SU`, `COLLABORA_CON`, `PROPOSTA_PER`, `BLOCCA`, `RISOLTO_DA`, `GENERATO_DA`, `COLLEGATO_A`.

`SYSTEM_PROMPT` impone al modello il formato JSON, i nomi validi e le regole per riconoscere anche relazioni implicite. `extract_entities_and_relations()` invia la nota al modello con risposta JSON obbligatoria, prova fino a tre volte e converte il testo JSON in un dizionario Python.

Il modulo non scrive nel database: produce soltanto dati strutturati. La persistenza è responsabilità di `core.db`.

### `core/tools.py`

È il dispatcher delle tool call generate da Groq.

Responsabilità:

- raccogliere gli strumenti esposti da tutti i client MCP;
- convertire i modelli MCP nello schema che Groq si aspetta;
- cercare quale client possiede lo strumento richiesto;
- decodificare gli argomenti JSON;
- eseguire `call_tool()`;
- estrarre il testo dalla risposta MCP;
- trasformare errori JSON, errori MCP ed eccezioni in risultati leggibili dal modello.

È separato da `core.chat` perché il ciclo conversazionale non deve conoscere i dettagli del protocollo MCP.

## Configurazione

Creare un file `.env` nella root del progetto con almeno:

```env
GROQ_API_KEY=la_tua_chiave
CLAUDE_MODEL=nome_del_modello_usato_dalla_chat
GROQ_MODEL=nome_del_modello_usato_per_estrarre_entita
USE_UV=0
```

`CLAUDE_MODEL` e `GROQ_MODEL` possono anche coincidere, ma hanno responsabilità diverse: il primo risponde all'utente e decide quando usare gli strumenti, il secondo struttura le note.

## Avvio

Con l'ambiente virtuale e le dipendenze installate:

```powershell
python main.py
```

Con `USE_UV=1` il processo MCP viene avviato tramite `uv`:

```powershell
$env:USE_UV = "1"
uv run main.py
```

Il file `pyproject.toml` contiene le dipendenze attualmente usate: Groq, MCP, `prompt-toolkit` e `python-dotenv`. La dipendenza Anthropic è stata rimossa perché il codice non la importa.
