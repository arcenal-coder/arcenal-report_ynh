# Lot API / MCP Report — 20 octobre 2026

## Périmètre autorisé

MCP intégré au processus applicatif YunoHost, lecture seule, authentification
Bearer dédiée et révocable. API REST machine équivalente, réutilisant le même
contrôle de droits et les mêmes sélections de données. Aucune publication ou
connexion au serveur réel dans ce lot. Conserver les travaux locaux précédents.

Transport : Streamable HTTP, réponses JSON, sans sessions ni flux SSE serveur.
Ne pas annoncer la prise en charge de l'ancien transport HTTP+SSE. Références :
https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
et https://modelcontextprotocol.io/specification/2025-06-18/server/tools.

Authentification : jetons aléatoires, empreintes SHA-256 en base, valeur montrée
une fois à l'administrateur, expiration et révocation immédiate. Chaque jeton
possède une liste explicite de missions (aucun wildcard) et de portées de lecture.
Les fichiers audio/photo et les brouillons ne sont pas exposés. Les transcriptions
exposées sont signalées comme non validées humainement.

Les routes machine seules contournent SSO via une permission YunoHost dédiée ;
leur authentification Bearer reste obligatoire, même si une session SSO existe.
La gestion des accès a sa propre permission admins et exige une identité SSO
ainsi qu'un en-tête de rôle imposé par Nginx, jamais fourni par le navigateur.
Aucune permission globale YunoHost, aucun accès direct aux fichiers ni SQL libre.

## Parcours et visibilité avant développement

| Acteur | Déclencheur et écran | Données / action | Preuve / sortie |
| --- | --- | --- | --- |
| Administrateur YunoHost | Tuile Connexions → écran intégrations | URL calculée depuis la configuration serveur, missions, portées, création confirmée | Jeton montré une fois, audit sans secret |
| Administrateur YunoHost | Liste des accès | Révocation confirmée d'un accès nommé | Accès révoqué immédiatement, message et audit |
| Hermes | Appel MCP ou REST avec Bearer | Uniquement outils et missions autorisés ; texte traité comme donnée | Résultat paginé, audit métadonnées |
| Équipier | Écran rapport existant | Brouillon, validation explicite, consultation figée et reprise | Historique existant conservé |
| Candidat, Manager, RH, Direction, QSSE, CRP | Aucun profil nouveau | Pas de droit d'administration induit par le nom du rôle | Accès gestion refusé hors permission admins |

Notifications : messages locaux uniquement, aucun envoi automatique à Hermes ou
au client. Les portées machine ne remplacent pas les futurs droits par équipier
et poste. Postes, passation et REX restent hors de ce lot.

## Retour Report → Hermes

Réutiliser le contrat existant de l'API d'agents centrale (route query), pas le
formulaire d'ajout de serveur MCP. Agent et application Report doivent être
déclarés côté ARCenal Agent ; ne pas emprunter les accès ARC/ATS. Configuration
serveur uniquement, désactivée sans configuration et autorisations explicites.
Le client et le dialogue de correction dans Report sont implémentés et testés
sans envoi de données réelles. Leur présence ne prouve pas l'intégration centrale
sur le serveur installé. Chaque proposition s'appuie sur le brouillon courant ;
elle ne l'écrit pas automatiquement et ne constitue pas un chat persistant.

## Contrôles de recette

- Nominal MCP : initialize, notification initialized, ping, tools/list, tools/call.
- REST et MCP : mêmes droits, pagination et résultats, lecture seule.
- Refus : jeton absent/erroné/expiré/révoqué, mission hors périmètre, portée
  absente, écriture, URL avec secret, Origin inconnu, message invalide ou trop grand.
- Gestion : refus sans identité admin, sans confirmation, depuis une autre origine.
- Tests de concurrence, limitation de débit partagée entre workers, pas de secret
  dans les listes ni les événements d'audit.
- Packaging : modules copiés, routes Nginx, permissions et sauvegarde de la base.
- Recette réelle YunoHost et Hermes : NON EXÉCUTÉE avant déploiement autorisé.
