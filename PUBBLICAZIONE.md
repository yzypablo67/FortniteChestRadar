# Pubblicazione su GitHub

Repository: https://github.com/yzypablo67/FortniteChestRadar
Release: https://github.com/yzypablo67/FortniteChestRadar/releases/tag/v0.2.0

I sorgenti includono configurazione di esempio, test sintetici, guida e licenze. La configurazione locale `config.json`, cache, catture e diagnostiche sono escluse dal controllo versione. Gli archivi della release sono puliti e non contengono la calibrazione privata.

## Aggiornare una release

1. Esegui i test descritti nel README e ricostruisci con build_windows.py su Windows.
2. Estrai e verifica il pacchetto; conserva insieme EXE e _internal.
3. Genera lo ZIP Windows e quello dei sorgenti, escludendo .git, config.json, cache, diagnostiche e cartelle di build dai sorgenti.
4. Aggiorna SHA256SUMS.txt e le note della release. Pubblica solo gli archivi puliti.

Non caricare Programma o Archivio_privato, che possono contenere configurazione e materiali personali.

## Altri hosting

Il §2(1)(7) delle condizioni Codeberg attualmente disponibili su https://codeberg.org/Codeberg/org/src/branch/main/TermsOfUse.md vieta progetti prevalentemente generati con AI. Questo progetto usa tale assistenza e non è stato caricato lì.

L'immagine del forziere è esclusa dalla licenza MIT del codice; attribuzioni e limiti sono in THIRD_PARTY.md.
