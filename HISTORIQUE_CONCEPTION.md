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

## 0.1.2 — 12 octobre 2026

- redirection Nginx explicite du chemin d’application sans barre finale vers `/arcenal-report/`, afin d’éviter une réponse 404 après installation.

## POC rapport local — 12 octobre 2026

- génération locale d’un brouillon de rapport de fin de poste depuis les notes, photos et transcriptions disponibles ;
- édition et sauvegarde du brouillon dans la base SQLite ;
- mise en page imprimable pour l’export PDF depuis le navigateur.

## 0.2.0 — 12 octobre 2026

- brouillon éditable avec nom de l’équipier et export Word avec logo ONYX et photos en annexe ;
- ouverture du client mail avec le contenu du rapport ;
- collecte météo géolocalisée au moment de la génération, messages indicatifs vent, pluie et orage ;
- ajout de notes texte, photo et vocal directement accessible ;
- intégration Hermes prévue, génération IA désactivée ;
- initialisation et migration SQLite au démarrage du service YunoHost, compilation autonome de Whisper et identité SSO transmise au serveur ;
- données locales, documents de test et fichiers déposés exclus de la publication GitHub.

## 0.2.1 — 20 octobre 2026 — correctif préparé localement

- attribution du binaire Whisper et de son dossier au compte de l’application avant exécution ;
- contrôle des exécutables et de la lecture du modèle avant conversion ;
- remontée dans l’interface des erreurs de conversion, de transcription et de permission ;
- relance possible des anciens enregistrements sans transcription ;
- tests de régression des permissions du paquet et du traitement audio ; recette sur serveur à confirmer.

## Principes de déploiement

- Le code applicatif est installé dans `/var/www/arcenal_report` par YunoHost.
- Les données de mission et les fichiers déposés restent séparés dans `/var/lib/arcenal_report`.
- Une mise à jour remplace uniquement le code ; elle conserve les données métier et les pièces jointes.
- Le paquet est prévu pour le catalogue privé ARCenal Store ; il n’est pas publié dans le catalogue communautaire YunoHost.

## 20 octobre 2026 — Report 0.3.0 Preview : API, MCP et validation

- Serveur MCP Streamable HTTP et API REST machine en lecture seule, avec droits
  explicites par mission, portées, expiration, révocation et limitation de débit.
- Écran d'administration YunoHost, URL publique et jeton affiché une seule fois.
- Client de correction Hermes configurable, confirmations d'envoi et
  d'application, puis validation séparée du rapport. Identité Report centrale
  encore à déclarer avant activation réelle.
- Historique figé des rapports et reprise motivée en copie modifiable.
- 63 tests applicatifs, interopérabilité client MCP officiel et recette UI avec
  SSO/Hermes simulés ; 25 tests catalogue et CI GitHub réussis.
- Version `0.3.0~ynh1`, tag `v0.3.0`, SHA applicatif
  `1535cd9866b6753a9bf335698b9c399b5ff1e5cb`, publication Preview et miroir
  catalogue vérifiés. Aucun changement stable. Installation YunoHost confiée à
  Damien à sa demande, NON EXÉCUTÉE par l'agent.
