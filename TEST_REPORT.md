# Vérification ARCenal REPORT 0.2.0

Date : 12 octobre 2026. Publication GitHub et catalogue preview autorisée par l’utilisateur. Cette publication ne constitue pas une validation du déploiement YunoHost.

| Contrôle | Résultat | Preuve ou limite |
| --- | --- | --- |
| Linter officiel YunoHost | NON_EXÉCUTÉ | Étape prévue dans GitHub Actions, non bloquante ; résultat distant à vérifier. |
| Compilation Python | RÉUSSI | Modules importés et exécutés avec Python 3.12 dans les tests locaux. |
| Syntaxe JavaScript | RÉUSSI | `node --check static/app.js` |
| Syntaxe des scripts de cycle de vie | RÉUSSI | `bash -n scripts/*` |
| Tests applicatifs et météo | RÉUSSI | 23 exécutions de tests ; export DOCX, auteur, édition du rapport, scénarios météo et échec réseau. Certains tests API sont hérités dans la suite météo. |
| Rendu Word ONYX | RÉUSSI | Document local rendu et pages inspectées : logo, chronologie, annexes photographiques. |
| Catalogue preview | RÉUSSI | Génération avec les scripts du catalogue et 14 tests du catalogue réussis. |
| Installation YunoHost neuve et accès web | NON_EXÉCUTÉ | Aucun serveur de recette YunoHost utilisé pendant cette publication. |
| Mise à jour YunoHost et migration persistante | NON_EXÉCUTÉ | Initialisation SQLite déclarée dans ExecStartPre ; à vérifier sur serveur de recette. |
| Sauvegarde et restauration YunoHost | NON_EXÉCUTÉ | Scripts examinés ; cohérence de la sauvegarde d’une base active à vérifier en recette. |
| Retrait et réinstallation | NON_EXÉCUTÉ | Syntaxe vérifiée ; cycle de vie réel à valider. |
| Permissions et SSO | NON_EXÉCUTÉ | Identité YunoHost transmise par Nginx ; droits réels et nom complet à valider sur serveur. |
| Transcription Whisper réelle | NON_EXÉCUTÉ | Modèle et binaire non installés sur le poste de développement. |
| Position et météo réelles | NON_EXÉCUTÉ | Service externe simulé dans les tests ; autorisation navigateur et réseau du serveur à valider. |

## Livraison et retour arrière

Version : `0.2.0~ynh1`, tag GitHub `v0.2.0`. Diff : rapports éditables, DOCX ONYX, auteur, mail et météo, dépendances et démarrage YunoHost. Hermes reste désactivé.

Les fichiers `data/` sont exclus du dépôt : base locale, audios, photos et exports ne sont pas publiés. La météo transmet uniquement les coordonnées approximatives à Open-Meteo.

Avant une mise à jour serveur, conserver une sauvegarde YunoHost complète de l’application. En cas d’échec, restaurer cette sauvegarde, incluant code et données. Ne pas supprimer les données pour réinstaller. La version précédente de référence est `0.1.2~ynh1` au commit `f0aa19d7b0740c472e526d4e18051a931ba8e670`.

Le modèle de manifeste mentionné par le skill Packaging n’est pas présent dans son installation locale ; le manifeste existant a été conservé et examiné. La recette complète reste nécessaire avant une diffusion stable.

## Correctif Whisper 0.2.1 préparé le 20 octobre 2026

Défaut signalé : transcription inopérante dans l’application publiée. Cause constatée dans le code livré : `whisper-cli` copié par root, mode `750`, sans transfert de propriété au compte du service. Le compte applicatif ne dispose donc pas de l’exécution lorsque le binaire appartient à root:root. Sans accès aux journaux du serveur, les autres causes restent ouvertes.

Correction : transfert récursif du dossier `bin` au compte applicatif dans le helper appelé à l’installation, la mise à jour et la restauration. Précontrôle de lecture du modèle et disponibilité des exécutables. Diagnostic renvoyé et affiché pour les notes vocales en échec ; anciens enregistrements relançables.

| Contrôle | Résultat | Preuve ou limite |
| --- | --- | --- |
| Linter officiel YunoHost | NON_EXÉCUTÉ | Indisponible localement. |
| Syntaxe JavaScript, compilation Python, scripts Bash | RÉUSSI | `node --check`, `py_compile`, `bash -n`. |
| Tests de régression | RÉUSSI | 28 exécutions, dont 5 nouveaux tests : droits du binaire, exécutable non accessible, chemin nominal, erreur FFmpeg, modèle manquant. |
| Diff | RÉUSSI | `git diff --check` et revue ciblée du helper, du traitement et des messages échappés dans l’interface. |
| Installation, upgrade, sauvegarde, restauration, retrait sur YunoHost | NON_EXÉCUTÉ | Serveur non accessible dans cette session. |
| Transcription vocale réelle | NON_EXÉCUTÉ | Commandes de transcription simulées dans les tests ; modèle et binaire absents localement. |

Publication, tag et promotion Preview autorisés par l’utilisateur le 20 octobre 2026. Candidate : `0.2.1~ynh1`, branche `preview`, tag `v0.2.1`. Avant application sur serveur : sauvegarde complète de l’application. Validation attendue : relancer une note existante, vérifier le texte et son intégration dans un rapport. En cas d’échec, conserver le diagnostic affiché ; ne pas effacer l’audio. Retour arrière par restauration de la sauvegarde applicative complète. La non-conformité reste ouverte jusqu’à cette recette.
