# Historique de conception — ARCenal REPORT

## 0.1.0 — 9 octobre 2026

- création du paquet YunoHost `arcenal_report` à partir du socle validé ARCenal DRAW ;
- application WSGI Python et SQLite dédiée à la main courante de mission ;
- ajout de notes texte, photos et notes vocales avec contrôle de type et de taille ;
- stockage persistant dans le répertoire de données YunoHost, inclus dans les sauvegardes ;
- authentification SSO gérée par YunoHost et reverse proxy Nginx ;
- scripts d’installation, de mise à jour, de suppression, de sauvegarde et de restauration ;
- vérifications automatisées du code, des tests et des scripts à chaque dépôt GitHub.

## POC transcription locale — 12 octobre 2026

- intégration de `whisper.cpp` et du modèle local `base` ;
- conversion audio par `ffmpeg`, transcription française en tâche de fond et stockage du texte lié à la note vocale ;
- suivi d’état dans l’interface et possibilité de relancer une transcription indisponible ou échouée.

## Principes de déploiement

- Le code applicatif est installé dans `/var/www/arcenal_report` par YunoHost.
- Les données de mission et les fichiers déposés restent séparés dans `/var/lib/arcenal_report`.
- Une mise à jour remplace uniquement le code ; elle conserve les données métier et les pièces jointes.
- Le paquet est prévu pour le catalogue privé ARCenal Store ; il n’est pas publié dans le catalogue communautaire YunoHost.
