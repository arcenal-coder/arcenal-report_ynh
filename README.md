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

## POC local exploitable

Lancer `python3 app.py`, puis ouvrir <http://127.0.0.1:8080>. Le POC permet de créer des notes, d’ajouter une photo ou un enregistrement vocal, puis de générer un brouillon de rapport de fin de poste. Le brouillon est éditable, sauvegardé dans SQLite et imprimable en PDF depuis le navigateur.

Le bouton **Télécharger Word modifiable** sauvegarde les corrections et exporte un `.docx` ONYX avec les photos en annexe. Le moteur de génération IA est prévu pour une intégration ultérieure et reste désactivé. Pour l’export local, le runtime Python doit disposer de `python-docx` et `Pillow` ; le paquet YunoHost déclare ces dépendances.

La génération du rapport demande la localisation du navigateur pour ajouter les prévisions du jour via Open-Meteo (coordonnées arrondies à deux décimales). La date météo est indiquée séparément de la date de mission. Les messages du POC sont calculés selon les seuils vent 50 km/h ou rafales 60 km/h, précipitations 1 mm/jour (fortes 10 mm/jour), et codes d’orage. Ce ne sont pas des bulletins de vigilance officiels. Refus de localisation ou panne réseau : le rapport reste générable et indique l’absence de météo. Les conditions de service du fournisseur devront être validées avant exploitation commerciale.

## API disponible

- `GET /api/v1/missions`
- `GET /api/v1/missions/{mission_uuid}`
- `GET /api/v1/missions/{mission_uuid}/entries`
- `POST /api/v1/missions/{mission_uuid}/entries` avec `{ "content": "..." }`
- `POST /api/v1/missions/{mission_uuid}/photos` en `multipart/form-data`
- `POST /api/v1/missions/{mission_uuid}/audio` en `multipart/form-data`
- `GET /api/v1/entries/{entry_uuid}/file`

La documentation exploitable est dans [`openapi.yaml`](openapi.yaml).

La transcription locale utilise Whisper.cpp lorsqu'il est installé et configuré.
Le rapport factuel reste disponible sans IA. Les pièces jointes restent attachées
à la mission ; les propositions IA nécessitent une configuration et une
confirmation explicites.

## Candidate 0.3.0 — API et MCP

Le prochain paquet intègre un serveur MCP en lecture seule, une API REST machine
avec jetons limités aux missions choisies et un écran de gestion réservé aux
administrateurs YunoHost. Le client de correction Hermes est configurable, sans
activation ni transmission par défaut. Les rapports validés restent figés et
peuvent être repris en nouvelle version.

Voir [le guide de connexion et les limites de recette](INTEGRATION_GUIDE.md).
Cette candidate vise le canal Preview. La publication et la recette serveur sont
tracées dans `.arcenal/DELIVERY_REPORT.md` ; une publication ne prouve pas une
installation ou une connexion Hermes réussie.
