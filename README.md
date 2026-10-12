# ARCenal REPORT

Application ARCenal de main courante terrain : missions, notes texte, photos et notes vocales. Le projet est livré comme paquet YunoHost v2, prêt à être référencé dans l’ARCenal Store.

L’historique des versions et les choix de déploiement sont dans [HISTORIQUE_CONCEPTION.md](HISTORIQUE_CONCEPTION.md).

## Lancer localement

```sh
python3 app.py
```

Ouvrir [http://127.0.0.1:8080](http://127.0.0.1:8080).

Un aperçu interactif de la cible finale, utilisant uniquement des données de démonstration, est disponible sur [http://127.0.0.1:8080/final-preview.html](http://127.0.0.1:8080/final-preview.html).

La base SQLite est créée dans `data/main-courante.sqlite3` au premier démarrage et contient deux missions de démonstration.

## Installation YunoHost

Depuis l’administration YunoHost, choisir **Installer une application personnalisée**, puis fournir l’URL Git du dépôt ARCenal REPORT. En ligne de commande :

```sh
sudo yunohost app install https://github.com/arcenal-coder/arcenal-report_ynh.git --debug
```

Le paquet installe Nginx, Gunicorn, `ffmpeg` et `whisper.cpp` avec le modèle français local `base`. Une note vocale est convertie et transcrite sur le serveur ; ni l’audio ni le texte ne sont envoyés à un service externe. Le premier téléchargement du modèle ajoute environ 150 Mo et peut rallonger l’installation.

## Vérifications

```sh
python3 -m unittest discover -s tests -v
bash -n scripts/*
```

## API disponible

- `GET /api/v1/missions`
- `GET /api/v1/missions/{mission_uuid}`
- `GET /api/v1/missions/{mission_uuid}/entries`
- `POST /api/v1/missions/{mission_uuid}/entries` avec `{ "content": "..." }`
- `POST /api/v1/missions/{mission_uuid}/photos` en `multipart/form-data`
- `POST /api/v1/missions/{mission_uuid}/audio` en `multipart/form-data`
- `GET /api/v1/entries/{entry_uuid}/file`

La documentation exploitable est dans [`openapi.yaml`](openapi.yaml).

La transcription, les rapports, l'IA et les connecteurs externes ne font pas encore partie de l'application. Les photos et les enregistrements restent attachés à leur mission jusqu'à la génération et la validation du rapport de fin de mission.
