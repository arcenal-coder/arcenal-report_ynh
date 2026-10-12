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
