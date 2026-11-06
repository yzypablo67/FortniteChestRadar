# Fortnite Chest Radar · 0.2.0 sperimentale

Radar esterno per Windows x64 che confronta i pixel della minimappa con una mappa di riferimento. Mostra punti di possibile spawn dei forzieri, non lo stato dei forzieri nella partita.

## Avvio rapido

1. Scarica il pacchetto Windows dalla [pagina delle release](https://github.com/yzypablo67/FortniteChestRadar/releases/latest) e **estrai tutta la cartella** in Documenti. L'EXE richiede la cartella `_internal` accanto: non spostarlo da solo.
2. Apri `Configura.bat`, scegli lo schermo e seleziona la minimappa.
3. Apri `FortniteChestRadar.exe`. Per le mappe e l'aggiornamento dei punti serve una connessione Internet.
4. Premi **Aggiorna casse** per importare i punti Fortnite.GG e allinearli alla mappa API.
5. Usa Fortnite in finestra senza bordi, poi **Overlay F8**. Se la fase non è leggibile, conferma con F7 soltanto quando sei davvero in partita.

Leggi [GUIDA_CONFIGURAZIONE.md](GUIDA_CONFIGURAZIONE.md) per configurazione, limiti e problemi comuni.

## Funzioni

- Icona fornita dall'utente, caricata dall'originale 1920×1920 e ridimensionata con filtro Lanczos: nessun cerchio nero o linea di collegamento.
- Icone sulle coordinate reali 2D del dataset, senza spostamenti artificiali.
- Zoom progressivo nelle zone dense; freccia di orientamento e movimento interpolati.
- Pausa e conferma temporale per ridurre stime casuali; filtro HUD per prelobby, con limiti descritti nella guida.
- Cattura diagnostica locale e test offline dell'EXE.
- Confronto opzionale XFeat CPU: modello ONNX da 2.681.450 byte. Non modifica la posizione live.

## Risultato XFeat

Nella cattura reale salvata usata per il confronto, SIFT produce un allineamento e XFeat non supera i controlli. Non è dimostrato un miglioramento di precisione. SIFT resta il metodo attivo; l'orientamento usa la freccia bianca della minimappa, non XFeat. I tempi nel report dipendono dal PC e non misurano gli FPS del gioco.

## Sviluppo e verifica

Windows x64, Python 3.14 usato per il pacchetto verificato. Crea un ambiente virtuale e installa `requirements-build.txt`. Copia `config.example.json` in `config.json`, poi:

```powershell
python -m unittest discover -s tests -v
python radar.py --self-test
python build_windows.py
```

La build genera `dist/FortniteChestRadar/FortniteChestRadar.exe`. `build_windows.py` prepara anche guida, configurazione pulita e comandi nella cartella portatile. I test automatici usano terreno sintetico: non sono una certificazione del funzionamento in partita.

## Dati e privacy

Nessun accesso alla memoria del gioco o invio di comandi al gioco. Il controllo di primo piano legge il titolo della finestra. Le catture vengono elaborate localmente. Il programma scarica mappe e dati da servizi esterni; non carica screenshot. Le diagnostiche possono contenere parti dell'HUD: controllale prima di condividerle. Il pacchetto pubblico non contiene configurazione personale, mappe di partita, screenshot o chiavi API.

## Licenze e pubblicazione

Codice del progetto: MIT, salvo componenti terzi. Modello XFeat: Apache 2.0; vedi [THIRD_PARTY.md](THIRD_PARTY.md). L'immagine del forziere è materiale Fortnite fornito dall'utente, escluso dalla licenza MIT. Nessuna affiliazione con Epic Games o Fortnite.GG.

Il progetto è sviluppato con assistenza di strumenti AI. I limiti delle prove sono descritti in [RISULTATI_VERIFICA.txt](RISULTATI_VERIFICA.txt).

Repository: https://github.com/yzypablo67/FortniteChestRadar · [Release Windows](https://github.com/yzypablo67/FortniteChestRadar/releases/latest).
