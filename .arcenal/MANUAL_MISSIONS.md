# Lot — création manuelle des missions

Besoin confirmé le 20 octobre 2026 : créer une mission dans Report sur YunoHost,
avant une future synchronisation Dolibarr. Aucun échange Dolibarr dans ce lot.

Parcours : équipier connecté → accueil Mes missions → Créer une mission →
formulaire client/intitulé/référence facultative/date → confirmation Enregistrer
et ouvrir → mission persistée → main courante vide prête à saisir.
La référence vide est générée côté serveur. Un doublon explicite est refusé,
sans écrasement. Annuler ne crée rien. Notification locale de succès et erreurs
lisibles ; aucune notification externe. Les missions suivent la visibilité
actuelle partagée entre comptes autorisés à Report (pas de nouvelle séparation
par rôle ou affectation). Aucun rôle RH/Direction/QSSE/CRP ajouté.

Contrôles : session SSO et origine obligatoire pour toute création YunoHost ;
jetons machine exclus ; champs et date validés côté serveur ; persistance et
absence d'altération des missions existantes ; doublon et entrées invalides.
Chargement : liste vide distincte d'un échec, bouton Réessayer, reconnexion
proposée si session expirée. Aucun réensemencement ni effacement pour corriger.

Diagnostic associé : régression reproduite en 0.3.0, Basic transmis par le proxy
avec Remote-User rejeté avant lecture des missions. Basic est désormais ignoré
comme preuve d'identité ; l'identité SSO reste obligatoire. Cette reproduction
locale ne prouve pas à elle seule la cause sur l'instance onyx-ingenierie.com.

Installation, recette et données réelles YunoHost : non vérifiées à ce stade.

## Preuves locales — 20 octobre 2026

- Ruff ciblé, syntaxe JavaScript, compilation Python et diff : réussis.
- Suite unittest : 70 exécutions réussies (incluant tests hérités).
- Navigateur sur base temporaire et SSO simulé, avec en-tête Basic : création
  CLIENT RECETTE / Mission de test manuelle, ouverture, ajout d'une note,
  rechargement et présence dans la liste vérifiés. Référence doublon refusée
  avec message affiché et conservation du formulaire.
- Preuve visuelle : `evidence/manual-missions-recette.png`, données synthétiques.
- Refus automatisés : absence de session, absence/mauvaise origine, jeton MCP
  même accompagné d'une session, champs invalides, date invalide et doublon.
  Une création manuelle ne modifie pas les périmètres des jetons MCP existants.
- Revue séparée du diff : création paramétrée sans migration de schéma,
  échappement des libellés, aucune connexion Dolibarr et aucune suppression.
- Diffusion de ce lot : non publiée ; aucune installation sur le serveur.
