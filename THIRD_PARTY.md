# Componenti e attribuzioni

## Immagine del forziere

File `assets/chest.png`, originale 1920×1920 fornito dall'utente. Materiale legato a Fortnite / Epic Games, escluso dalla licenza MIT del codice. Nessuna affiliazione o approvazione. L'utente deve verificare i diritti di ridistribuzione prima della pubblicazione ampia. Il programma la ridimensiona per la visualizzazione, conservando il file originale.

## XFeat

XFeat: Accelerated Features for Lightweight Image Matching (CVPR 2024), Guilherme Potje, Felipe Cadar, Andre Araujo, Renato Martins, Erickson R. Nascimento. Progetto originale: https://github.com/verlab/accelerated_features — Apache 2.0.

Esportazione ONNX: DavideCatto/XFeat-ONNX, release V1.0.0, https://github.com/DavideCatto/XFeat-ONNX/releases/tag/V1.0.0 — Apache 2.0. Il modello preaddestrato viene usato senza modifiche.

`models/xfeat.onnx`: 2.681.450 byte; SHA256 `41336466bbbb09b701b815e33932c7da69cff6ab75a068230418468430482912`.

L'adattatore del progetto applica filtri geometrici e ritagli della mappa; non include il vecchio modello di riconoscimento visivo dei forzieri.

## Librerie e servizi

Versioni bloccate in requirements.txt e requirements-build.txt. Testi di licenza disponibili in `licenses/` e nei metadati distribuiti di Python, Tcl/Tk, OpenCV, NumPy, Pillow, MSS, Requests, ONNX Runtime/DirectML e dipendenze. PyInstaller include l'eccezione per distribuire applicazioni costruite con esso.

Mappe: https://fortnite-api.com/ ; punti e mappe: https://fortnite.gg/ . Questi contenuti vengono scaricati a runtime, non sono inclusi negli archivi pubblici. Servizi e formati possono cambiare; non fanno parte della licenza MIT del progetto.
