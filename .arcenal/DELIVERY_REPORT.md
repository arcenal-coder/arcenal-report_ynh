# Diffusion ARCenal REPORT 0.3.1 — Preview

Publication GitHub et Store Preview autorisée par Damien le 20 octobre 2026.
Installation sur son serveur laissée à Damien, sans déploiement automatique.

- Périmètre : création manuelle de mission depuis l'accueil (client, intitulé,
  référence facultative, date), contrôle des doublons et ouverture pour saisie.
  Correction de la confusion Basic SSO/Bearer machine et diagnostic des erreurs
  de chargement. Aucune connexion Dolibarr ajoutée.
- Version candidate : `0.3.1~ynh1`, branche `preview`, tag prévu `v0.3.1`.
- Preuves locales : `.arcenal/MANUAL_MISSIONS.md` ; 70 exécutions unittest,
  recette navigateur synthétique et vérifications de syntaxe/diff réussies.
- Compatibilité : schéma des missions inchangé, aucune suppression ; les accès
  MCP existants ne gagnent pas automatiquement de nouvelles missions.
- GitHub / Store : publication en cours, source et résultats à compléter.
- Installation et cycle de vie YunoHost réels : NON_EXÉCUTÉS. Sauvegarder avant
  mise à jour puis vérifier création, note, rechargement et accès MCP admin.
- Retour arrière : restaurer ensemble code et données depuis une sauvegarde
  YunoHost complète ; ne pas supprimer la base ni réinstaller pour contourner
  une erreur. La recette locale ne prouve pas la santé du serveur distant.

## Historique — diffusion 0.3.0

Date : 20 octobre 2026. Publication GitHub et ARCenal Store demandée explicitement
par Damien après développement. La cible reste Preview, sans promotion stable.

- Source : https://github.com/arcenal-coder/arcenal-report_ynh
- Branche : `preview` ; version `0.3.0~ynh1` ; tag annoté publié `v0.3.0`.
- Commit applicatif : `1535cd9866b6753a9bf335698b9c399b5ff1e5cb`,
  `feat: add scoped MCP and API integrations with report validation`.
- Contrôles locaux renouvelés : Ruff ciblé, syntaxe JavaScript, compilation
  Python, syntaxe Bash, 63 exécutions unittest et diff RÉUSSIS.
- Preuves : `.arcenal/API_MCP_VALIDATION.md` et `INTEGRATION_GUIDE.md`.
- Catalogue cible : `arcenal-systeme-catalogue`, entrée `arcenal_report`,
  préparation development puis promotion officielle ciblée vers Preview,
  branche source `preview` et SHA exact de la candidate.
- Publication GitHub : RÉUSSIE, push atomique de `preview` et `v0.3.0`.
  Tag annoté `5f60aa601eb901beadca44cc72458024519516cc`, source applicative
  `1535cd9866b6753a9bf335698b9c399b5ff1e5cb`. Préversion publiée :
  https://github.com/arcenal-coder/arcenal-report_ynh/releases/tag/v0.3.0.
- CI applicative : RÉUSSIE, run
  https://github.com/arcenal-coder/arcenal-report_ynh/actions/runs/39462209877.
- Préparation catalogue : PR nº30 fusionnée au commit
  `8ce2aea527a0c0c2e35016dec898fd5fa3400fb7`,
  https://github.com/arcenal-coder/arcenal-systeme-catalogue/pull/30.
  25 tests catalogue réussis, dont cohérence du paquet et promotion sélective.
- Promotion officielle Report uniquement development → preview : RÉUSSIE,
  workflow nº60, https://github.com/arcenal-coder/arcenal-systeme-catalogue/actions/runs/39462590727.
- Catalogue / Store Preview : RÉUSSI, commit catalogue
  `8c64aec78e69f819a221a052a2c42363f8ee1306`. Le flux canonique
  `main/preview/v3/apps.json` résout `arcenal_report` en `0.3.0~ynh1`, branche
  `preview`, révision `1535cd9866b6753a9bf335698b9c399b5ff1e5cb`, minimum
  YunoHost 12.1.17 et architectures amd64/arm64. Les fichiers stable n'ont pas
  changé et les autres versions Preview sont conservées.
- Miroir public du catalogue : publication RÉUSSIE, workflow nº280,
  https://github.com/arcenal-coder/arcenal-systeme-catalogue/actions/runs/39462624516.
- Installation et cycle de vie YunoHost réels : NON_EXÉCUTÉS. Aucune session
  d'administration YunoHost authentifiée ni sauvegarde serveur n'a été vérifiée.
  Damien a explicitement choisi d'effectuer lui-même l'installation. L'accès
  navigateur contrôlé affichait la page de connexion ; aucune mise à niveau,
  sauvegarde, modification de permission ou création de jeton réelle exécutée.
- Connexion au Hermes installé : NON_EXÉCUTÉE. Nécessite une identité Report
  dédiée côté ARCenal Agent ; le MCP et le client API ne créent pas ces droits.
- Retour arrière : sauvegarde complète avant upgrade ; restauration conjointe
  code/base/configuration. Recontrôler les jetons après restauration, qui peut
  précéder une révocation. Ne pas effacer les remontées ou réinstaller pour
  contourner une erreur de mise à niveau.

## Historique — diffusion 0.2.1

Date : 20 octobre 2026. Push, tag et promotion Preview autorisés par Damien dans cette conversation.

- Source : https://github.com/arcenal-coder/arcenal-report_ynh
- Branche de livraison : `preview`.
- Version : `0.2.1~ynh1` ; tag : `v0.2.1`. Le SHA exact est celui de ce tag, à vérifier par `git rev-list -n 1 v0.2.1`.
- Catalogue cible : `arcenal-systeme-catalogue`, canal `preview`, entrée `arcenal_report` avec le SHA exact du correctif et la branche `preview`.
- Contrôles locaux : syntaxe JavaScript, compilation Python, tests impactés (28 exécutions), syntaxe Bash et revue du diff RÉUSSIS.
- Périmètre : propriété et exécution du binaire Whisper, précontrôles, diagnostic et relance des notes existantes.
- Installation et recette de transcription YunoHost : NON_EXÉCUTÉES. À réaliser par Damien ou Guillaume après sauvegarde et mise à jour.
- Publication applicative RÉUSSIE : SHA `ebabb566213398ab942045b797a34e30a399cdb4`, branche distante `preview`, tag annoté `v0.2.1` vérifié après push.
- Préparation catalogue RÉUSSIE : demande de fusion https://github.com/arcenal-coder/arcenal-systeme-catalogue/pull/29 fusionnée au commit `a106035b42c5a55c88df3d1147f651d3f6fe2731`. Les 23 tests du catalogue passent localement.
- Promotion active development vers preview RÉUSSIE le 20 octobre 2026 : workflow officiel nº57, https://github.com/arcenal-coder/arcenal-systeme-catalogue/actions/runs/39396738273, ciblé uniquement sur `arcenal_report`. Toutes les étapes du job ont réussi, y compris l’actualisation du catalogue public.
- Résolution du flux `preview/v3/apps.json` vérifiée au commit catalogue `75ee5bc` : version `0.2.1~ynh1`, URL applicative attendue, branche `preview`, révision `ebabb566213398ab942045b797a34e30a399cdb4`.
- Installation et recette serveur : NON_EXÉCUTÉES ; la publication du catalogue ne prouve pas une transcription réelle réussie.
- Retour arrière : restauration de la sauvegarde YunoHost complète, incluant code et données ; ne pas effacer les notes vocales pour réinstaller.
