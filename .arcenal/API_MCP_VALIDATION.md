# Candidate 0.3.0~ynh1 — validation locale API / MCP

Date : 20 octobre 2026. État à la fin du développement local, avant publication.
La publication GitHub et Preview effectuée ensuite est tracée séparément dans
`DELIVERY_REPORT.md`. Aucun changement des accès du serveur réel effectué.

## Réalisé

- Serveur MCP intégré au WSGI et API REST machine, même service de lecture et
  mêmes droits de mission/portée. Aucun endpoint d'écriture MCP.
- Gestion des accès avec confirmation, expiration et révocation. URL publique
  serveur, empreinte seule en SQLite, valeur du jeton montrée une fois.
- Écran YunoHost réservé à admins, routes machine dédiées, vérification SSO pour
  les API navigateur et contrôle d'Origin pour les écritures en déploiement.
- Client du contrat central ARCenal Agent et parcours de correction dans Report,
  désactivés sans configuration/autorisation. Confirmation d'envoi puis
  confirmation d'application au brouillon, sans validation automatique.
- Achèvement du lot validation/historique commencé précédemment : consultation
  figée, garde serveur et triggers SQLite, reprise motivée, versions conservées,
  export Word ciblant le rapport réellement consulté et non un autre brouillon.
- Packaging : copie des nouveaux modules, permissions main/integrations/machine,
  routes Nginx, URL serveur et EnvironmentFile facultatif, UMask et fichiers de
  données protégés. Minimum YunoHost aligné sur les helpers 2.1 : 12.1.17.

## Contrôles exécutés

1. Ruff E9/F sur les modules et tests concernés : RÉUSSI.
2. Syntaxe des deux JavaScript, compilation Python, syntaxe Bash des scripts de
   cycle de vie, lecture TOML du manifeste et parsing YAML de l'OpenAPI : RÉUSSIS.
   Le parsing YAML n'est pas une validation exhaustive du schéma OpenAPI.
3. Suite unittest : **63 exécutions réussies**, dont des cas hérités de tests
   météo. Couverture : nominal, limites, refus, isolation mission, expiration,
   révocation, débit concurrent partagé, absence de secrets en base/audit,
   confirmation et conflits de correction/validation, migration additive.
4. Interopérabilité réseau locale avec le **client officiel Python MCP 1.30.0** :
   initialize → version 2025-06-18, notification initialized, découverte des
   cinq outils, lecture d'une mission autorisée et ping : RÉUSSIE.
   Base et jeton synthétiques temporaires. Aucun fournisseur IA contacté.
5. Navigateur sur `tests/preview_server.py` : chargement de l'administration,
   création confirmée d'un accès affiché masqué, révocation et état persistant
   Révoqué : RÉUSSIS. Demande de correction, proposition distincte, application
   confirmée, validation humaine puis rechargement en consultation figée avec
   identité SSO simulée : RÉUSSIS.
   Reprise motivée : prouvée par tests API ; pas déclarée recettée au navigateur.
   Capture sans secret : `evidence/mcp-recette.png`.
6. Revue séparée du diff, sans sous-agent : protection des routes et secrets,
   héritage des permissions, concurrence, chemins de packaging et non-écrasement.
   Corrections : dossier `web` servi derrière le contrôle admin en installation
   packagée ; export ciblé ; message de disponibilité Hermes cohérent ; rejet
   UTF-8/tailles et entrées invalides ; vérification d'un brouillon disparu.
   `git diff --check` : RÉUSSI.

## Limites et prérequis avant diffusion réelle

- Installation, upgrade, backup/restore et suppression sur YunoHost :
  **NON EXÉCUTÉS** ; seule la cohérence statique du paquet est contrôlée ici.
- Validation de la configuration Nginx par `nginx -t`, permission SSO effective,
  anti-usurpation des en-têtes depuis Internet et frontière entre comptes du
  même hôte : **NON EXÉCUTÉS**, instance YunoHost de recette nécessaire.
- L'API et la permission admins supposent un reverse proxy de confiance. Le
  port applicatif ne doit jamais être publié. La recette locale simule SSO et
  ne constitue pas une preuve de droits YunoHost réels.
- ARCenal Agent : agent Report, identité machine et routage dédiés à enregistrer
  côté central. Aucun emprunt d'identité ARC/ATS. Configuration sans outils
  et choix du fournisseur/confidentialité à valider avant transfert de données.
- Hermes réellement installé : **NON CONNECTÉ / NON RECETTÉ**. La preuve SDK
  ne démontre pas la version du client installé chez l'utilisateur.
- Historiques de dialogue persistant, postes multi-équipiers, alertes, passation
  et REX : non livrés par ce lot. Les droits équipier par poste ne sont pas
  remplacés par les portées du jeton machine.
- Les médias restent des originaux référencés ; les snapshots figent les textes
  et métadonnées, pas une archive binaire immuable des pièces jointes.

Avant upgrade : sauvegarde complète, vérification de l'accès SSO et des routes
machine, puis recette sur mission fictive. Rollback : restaurer code, base et
configuration cohérents. Une ancienne sauvegarde peut précéder une révocation :
réexaminer et révoquer les accès après restauration avant réouverture.

Verdict : **DÉVELOPPEMENT LOCAL VÉRIFIÉ — RECETTE YUNOHOST/HERMES REQUISE**.
