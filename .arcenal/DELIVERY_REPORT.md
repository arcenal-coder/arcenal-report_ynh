# Diffusion ARCenal REPORT 0.2.1

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
