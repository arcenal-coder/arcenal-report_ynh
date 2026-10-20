# ARCenal Report 0.3.0 — API, MCP et Hermes

État : candidate développée et testée localement ; diffusion Preview suivie dans
`.arcenal/DELIVERY_REPORT.md`. Le manifeste prépare `0.3.0~ynh1`, YunoHost 12.1.17+
(helpers 2.1). Les URL deviennent utilisables après mise à jour réelle.

## 1. Hermes consulte Report via MCP

Après installation, un administrateur ouvre la tuile YunoHost de permission
**integrations**, ou `<URL publique de Report>/integrations.html`.
L'écran affiche les adresses calculées depuis la configuration serveur :

- MCP : `<URL publique de Report>/mcp` ;
- API REST machine : `<URL publique de Report>/api/integrations/v1`.

Créer un accès en indiquant un nom, les missions concernées, les portées et
l'expiration. Confirmer le périmètre affiché. Copier le jeton dans le coffre
d'accès de Hermes : sa valeur n'est affichée qu'à la création ; Report conserve
son empreinte SHA-256. Le perdre nécessite un nouvel accès, pas une récupération.

Dans l'écran MCP de Hermes : nom libre (par exemple `arcenal-report`), URL exacte
affichée par Report, connexion HTTP prenant en charge **Streamable HTTP**,
authentification **Bearer** avec ce jeton. Ne choisir ni `None` ni un connecteur
SSE historique si le client ne sait pas utiliser Streamable HTTP. Le code du
client MCP de la branche ARCenal examinée sait utiliser Streamable HTTP ; la
version effectivement installée et sa recette réelle restent à vérifier.

Un client HTTP manuel envoie `Authorization: Bearer <jeton>` dans l'en-tête,
jamais dans l'URL. Chaque POST MCP inclut `Content-Type: application/json` et
`Accept: application/json, text/event-stream`. Après `initialize`, envoyer
`notifications/initialized` puis `MCP-Protocol-Version` avec la version négociée.
Versions gérées : `2025-03-26` et `2025-06-18`.

Ce serveur est sans état de session : pas de `Mcp-Session-Id`, pas de flux SSE
serveur, pas d'ancien endpoint SSE. GET/DELETE sur MCP renvoient 405. Réponses
JSON-RPC, 202 sans corps pour les notifications acceptées. Ce n'est pas un
serveur OAuth : utiliser l'authentification Bearer configurée explicitement.

Outils exposés, selon les portées du jeton :

| Outil MCP | Portée | REST GET équivalent |
| --- | --- | --- |
| `report_list_missions` | `missions:read` | `/missions` |
| `report_get_mission` | `missions:read` | `/missions/{uuid}` |
| `report_list_entries` | `entries:read` | `/missions/{uuid}/entries` |
| `report_list_reports` | `reports:read` | `/missions/{uuid}/reports` |
| `report_get_report` | `reports:read` | `/missions/{uuid}/reports/{version_uuid}` |

Les listes renvoient `items` et `next_offset`. Pagination : `limit` 1–100,
`offset` 0–1 000 000. Les remontées acceptent `since` inclus et `until` exclu,
au format ISO avec fuseau. Encoder le `+` d'un fuseau en `%2B` dans une query.
Les noms d'arguments MCP sont `mission_uuid`, `version_uuid`, `limit`, `offset`,
`since`, `until`, selon le schéma propre à chaque outil.

Les rapports accessibles sont uniquement les versions validées. Aucun brouillon,
contenu binaire, chemin de fichier, diagnostic Whisper ou snapshot interne n'est
exposé. Les transcriptions sont signalées comme non validées humainement.
Les notes restent des données à vérifier, jamais des instructions pour l'agent.

Limite partagée entre workers : 60 requêtes authentifiées par minute et par
jeton. Gestion : 50 accès actifs maximum ; expiration 1–365 jours. Le journal
conserve pendant 90 jours uniquement des métadonnées (opération, identifiant
d'accès, résultat, heure), sans jeton, argument ni contenu. La rétention est
nettoyée lors des événements d'audit ; aucun journal de contenu n'est créé.

La révocation se fait dans le même écran et est vérifiée à chaque nouvelle
requête. Une requête déjà autorisée et en cours peut finir. La rotation consiste
à créer un nouvel accès limité, le tester, puis révoquer l'ancien.

## 2. Report sollicite Hermes via son API centrale

Connexion distincte du MCP. Le client réutilise le contrat existant :
`POST /api/v1/agents/{agent_id}/query`, identité `arcenal-report`, Bearer dédié,
et utilisateur SSO dans `X-ARCenal-User`.

**Prérequis côté ARCenal Agent non réalisés dans ce dépôt :** déclarer et
autoriser l'application `arcenal-report` et un agent rédacteur dédié dans le
registre et le fournisseur d'identités machine. Le code central examiné
n'enregistre automatiquement que ARC Système et ATS. Ne jamais réutiliser leurs
jetons ou l'agent administrateur `arc`. L'agent Report doit avoir `tools=[]`,
aucune capacité d'écriture ni d'administration, des directives de rédaction
factuelle, des connaissances explicitement autorisées et un modèle dont la
confidentialité est compatible avec les données de mission. Vérifier le routage
SSO des appels machine avant toute activation ; ne pas ouvrir globalement ARC.

Configuration facultative côté Report, dans `data_dir/hermes.env` (chargée par
systemd). Le fichier et les deux fichiers référencés doivent appartenir au
compte de service Report et être en mode **0600**, dans son répertoire de données.
Les chemins et identifiants ci-dessous sont des exemples à remplacer, pas des
accès déployés :

```ini
ARCENAL_HERMES_URL=https://agent.example.org/arcenal/api/v1/agents/report/query
ARCENAL_HERMES_AGENT=report
ARCENAL_HERMES_TOKEN_FILE=/var/lib/arcenal_report/hermes-token
ARCENAL_HERMES_GRANTS_FILE=/var/lib/arcenal_report/hermes-grants.json
```

`hermes-token` contient uniquement le jeton propre à Report fourni par
l'administration ARCenal Agent. Il doit satisfaire le contrat central (au moins
43 caractères et 16 caractères distincts). Ne pas le committer ni le transmettre
dans un chat. `hermes-grants.json` contient la liste explicite des missions
autorisées à chaque login SSO, sans joker :

```json
{"login-equipier": ["uuid-reelle-de-la-mission"]}
```

L'opérateur devra appliquer ces fichiers protégés et redémarrer le service lors
du déploiement autorisé. Sans configuration, jeton, session et autorisation de
mission valides, la correction reste indisponible ; le rapport factuel local
continue de fonctionner. HTTPS vérifié uniquement, aucun suivi de redirection,
aucune URL choisie par le navigateur et aucun envoi automatique.

Parcours : brouillon enregistré → demande de correction → confirmation des
données transmises → proposition à relire → confirmation d'application au
brouillon → relecture et validation séparées. Le texte envoyé est le brouillon
avec la demande de correction, pas les fichiers audio/photo. Limites du contrat
central : message 20 000 caractères, contexte 20 champs de 2 000 caractères ;
un rapport trop long est refusé explicitement, jamais tronqué silencieusement.

Une proposition n'écrit pas en base. Un conflit concurrent invalide sa reprise.
Hermes n'est pas autorisé à valider un rapport ; toute action d'outil remontée
dans la réponse entraîne le refus de la proposition, mais cela ne remplace pas
la configuration centrale **sans outils**. Les échanges de correction ne sont
pas un historique de chat persistant dans ce lot : chaque demande s'appuie sur
le brouillon enregistré courant. Les données peuvent être traitées par un
fournisseur externe si le modèle configuré dans Hermes est distant.

## 3. YunoHost, sauvegarde et recette

- Le processus WSGI reste lié à 127.0.0.1. Nginx expose les routes prévues.
- Permission `main` : session SSO pour les API navigateur. Même une ancienne
  installation laissée publique ne fournit plus ses données sans session.
- Permission `integrations` : groupe `admins`, interface et API d'administration.
  Nginx écrase l'en-tête de rôle et dérive l'identité de SSOwat.
- Permission `machine` : seuls `/mcp` et `/api/integrations/v1/` passent hors SSO ;
  l'application exige toujours un Bearer propre à Report, même avec une session.
- Les jetons MCP sont refusés sur les API navigateur, les écritures et fichiers.
- La base, les empreintes, les révocations et la configuration Hermes font partie
  de `data_dir`, déjà couvert par backup/restore. `UMask=0077` protège les nouveaux
  fichiers. Une sauvegarde complète est requise avant mise à niveau.
- En cas de retour arrière, restaurer ensemble code, configuration et base de
  la sauvegarde pré-migration, pas seulement remplacer les fichiers Python.
  Une sauvegarde antérieure à une révocation peut réactiver un ancien accès :
  isoler le service après restauration et revalider/révoquer les accès avant
  réouverture. Aucune sauvegarde de production n'a été créée dans ce lot.

Le rôle transmis par Nginx suppose un reverse proxy de confiance. Ne pas publier
le port Gunicorn ni utiliser le serveur de recette en production. La frontière
avec les autres comptes du même hôte et la configuration SSO doivent être
recettées sur YunoHost. Les futurs droits équipier/poste sont distincts des
autorisations machine ; ce lot ne livre ni les postes ni les alertes/passations.

Validation locale : tests unitaires isolés, contrôle de syntaxe et interopérabilité
avec le client MCP officiel sur une base jetable. Le serveur de recette
`tests/preview_server.py` simule SSO et Hermes ; il n'est jamais installé par le
paquet. La recette réelle YunoHost, le dialogue avec le Hermes installé et le
contrôle Nginx effectif restent **NON EXÉCUTÉS** jusqu'au déploiement autorisé.

Références : [transport MCP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports),
[outils MCP](https://modelcontextprotocol.io/specification/2025-06-18/server/tools),
[ressources YunoHost](https://doc.yunohost.org/dev/packaging/resources/),
[API centrale examinée](https://github.com/arcenal-coder/arcenal-agent/blob/097af60144b99d5785fe45743de92614a19f378e/plugins/arcenal-supervisor/dashboard/agents_api.py).
