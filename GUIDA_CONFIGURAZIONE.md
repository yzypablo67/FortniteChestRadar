# Configurare Chest Radar

## 1. Installa la cartella portatile

Estrai lo ZIP Windows in una cartella scrivibile, per esempio `Documenti/ChestRadar`. Conserva insieme `FortniteChestRadar.exe`, `_internal`, `config.json` e gli altri file. Non serve installare Python per usare l'EXE. La build non è firmata: controlla provenienza e SHA256; non disattivare le protezioni di Windows.

## 2. Seleziona la minimappa

Apri Fortnite e mostra la minimappa normale, non la mappa a schermo intero. Apri `Configura.bat` oppure il pulsante **Configura minimappa** nel pannello.

Scegli il monitor. Premi il pulsante, torna a Fortnite entro tre secondi, quindi traccia il rettangolo attorno alla sola minimappa. Non includere cornice, contatori sotto la mappa o bussola. Invio salva; C o Esc annulla. Il giocatore deve trovarsi al centro del ritaglio. Chiudi e riapri il radar dopo aver salvato. Ripeti quando cambi risoluzione, scala HUD o monitor.

## 3. Carica i punti delle casse

Il programma scarica una mappa pulita tramite Fortnite-API. Premi **Aggiorna casse** per importare Fortnite.GG e allinearne le coordinate alla mappa usata per il matching. Attendi il completamento. Una mappa o stagione diversa può produrre un errore o punti errati. Il formato del sito può cambiare.

Non è necessaria una chiave API per questo percorso. L'opzione storica `api_key` è vuota e non serve per Fortnite.GG. Nessun dataset personale è incluso nella distribuzione.

## 4. Attiva l'overlay

Usa la modalità finestra senza bordi di Fortnite. F8 alterna pannello e overlay; F9 sblocca l'overlay e consente di trascinarlo dal titolo; premi ancora F9 per renderlo trasparente ai clic. F10 nasconde o mostra l'overlay. Evita di sovrapporlo alla minimappa originale.

La compatibilità con fullscreen esclusivo e anti-cheat non è stata certificata.

## 5. Leggi la mappa

L'icona indica un **punto di spawn del dataset**, non conferma che un forziere sia comparso o sia ancora chiuso. Nessuna quota, piano dell'edificio o proiezione 3D è disponibile. Più punti vicini producono uno zoom più ravvicinato, fino al limite di 80 pixel della mappa di riferimento. Punti coincidenti o su piani diversi possono sovrapporsi: lo zoom non può separarli correttamente senza dati aggiuntivi.

La mappa rimane orientata a nord. La freccia rappresenta la direzione della freccia bianca della minimappa; non garantisce la direzione della telecamera in ogni situazione. Quando non è leggibile compare un punto.

## Comandi

| Comando | Funzione |
| --- | --- |
| F6 | Alterna zoom in base alla densità e zoom libero |
| F7 | Pausa/riprendi; conferma manuale della partita se il controllo HUD lo richiede |
| F8 | Pannello / overlay |
| F9 | Sblocca / blocca l'overlay |
| F10 | Nascondi / mostra l'overlay |
| Rotella, + e − | Regola lo zoom |
| Manuale | Consente di impostare la posizione con un clic sulla mappa |

F4 e F5 non raccolgono esempi e non avviano il vecchio modello per riconoscere i forzieri. Quella sperimentazione è stata rimossa dall'app corrente.

## XFeat leggero: prova separata

**Confronta XFeat** usa l'ultima minimappa catturata e la mappa corrente. Crea nuovi matcher e un report locale; non corregge la posizione live e non invia immagini online. Se non esiste ancora una cattura, entra in partita e attendi un tentativo di matching.

XFeat non è stato migliore sulla cattura di confronto disponibile: per questo non è attivo nel rilevamento. Per ripetere il confronto su immagini salvate:

```powershell
.\FortniteChestRadar.exe --compare-xfeat --map mappa.png --minimap minimappa.png --out risultati
```

Il confronto misura quattro passaggi ed esclude il primo dalla mediana. Non misura precisione senza coordinate di riferimento indipendenti. Per validarlo servono più posizioni note, scene diverse e riferimenti angolari verificati.

## Problemi comuni

- **Prelobby / attesa:** il radar attende il controllo HUD e tre letture geometricamente coerenti. Il filtro OCR non è uno stato ufficiale del gioco. Non è stato verificato con una vera cattura di prelobby. Se OCR non è disponibile, F7 conferma manualmente solo quando sei in partita.
- **Matching rifiutato:** controlla ritaglio, monitor, modalità e versione della mappa. Evita mappa a schermo intero e minimappa coperta. Usa Diagnostica per salvare il tentativo.
- **Nessuna cassa:** completa Aggiorna casse e controlla che i dati corrispondano alla mappa. Non inventare coordinate né interpretare l'assenza di icone come prova che non ci siano casse.
- **Overlay invisibile:** F10, poi F8; prova finestra senza bordi. Se un tasto è occupato, usa i pulsanti del pannello. Un conflitto non disabilita più tutte le altre scorciatoie.
- **Monitor assente:** configura di nuovo la minimappa. L'overlay usa il monitor principale come ripiego, ma la cattura richiede una selezione valida.
- **Errore all'avvio:** consulta `startup_error.log`. Verifica che tutta la cartella `_internal` sia presente e che la cartella di installazione sia scrivibile.

## Verifica offline

Apri `Verifica.bat`. Controlla che `self-test.json` contenga `"ok": true`. Verifica matching su terreno sintetico, Tk, librerie e risorse; non valida riconoscimento in una vera partita. Nessun input viene inviato al gioco.

## Backup e aggiornamenti

Chiudi il radar. Conserva una copia privata di `config.json` e `cache` prima di aggiornare. Per mantenere la calibrazione, non sovrascrivere la tua configurazione con quella pulita distribuita agli altri. Le diagnostiche sono private: non pubblicarle automaticamente.
