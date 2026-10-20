# ARCenal Report — préparation Hermes

Statut : parcours validé dans la conversation le 20 octobre 2026 ; démarrage du
développement local autorisé. Connexion Hermes non disponible, aucune
transmission activée.

## Décisions complémentaires validées

- Main courante commune par mission, plusieurs équipiers et postes simultanés.
- Horaires de poste libres, y compris à cheval sur minuit ; rapport par poste.
- Remontées de poste ou partagées avec la mission ; alertes avec accusés de
  lecture individuels horodatés. Tout équipier de la mission peut résoudre une
  alerte, en conservant l'action et son auteur.
- Passation obligatoire à chaque prise de poste avant première saisie : résumé,
  consignes et alertes actives des postes précédents et concurrents. Signaler une
  nouvelle urgence reste possible sans franchir cette étape.
- Brouillon préparé par IA, dialogue de correction et édition directe, puis
  validation explicite par un équipier, pas nécessairement chef d'équipe.
- Consultation figée après validation ; copie éditable conservée. Toute reprise
  crée une nouvelle version, sans écraser le rapport validé.

## Lot local initial : validation et historique

Portée bornée : sécuriser les rapports existants au niveau mission. Les postes,
alertes, passations, dialogue IA et REX feront l'objet des lots suivants. Aucune
prétention de gestion par poste dans ce premier lot.

Parcours équipier depuis l'écran mission : brouillon visible et éditable →
confirmation nominative du texte exact → consultation figée et historique →
motif de reprise obligatoire → nouveau brouillon. La confirmation précise la
mission et la conséquence du verrouillage ; message de succès affiché localement,
aucune notification ni transmission externe. Les données visibles restent celles
de la mission. Aucun rôle Candidat, RH, Direction, QSSE ou CRP n'est ajouté ;
les droits fins par mission ne sont pas présents dans le POC et restent à
implémenter avant usage multi-équipiers en production. Le groupe YunoHost ouvre
l'accès mais ne constitue pas, à lui seul, une autorisation par mission.

Architecture : tables SQLite existantes conservées, ajout d'un registre de
validations avec texte, sources figées, auteur, date et numéro. Refus serveur de
modifier un rapport validé. Identité SSO prioritaire sur l'identité déclarative
locale (POC seulement). Pas de nouvelle dépendance ni modification plateforme.
Migration additive seulement ; tests sur bases temporaires, aucune migration
manuelle sur les données locales réelles. Sauvegarde complète avant déploiement,
retour arrière avec code et base cohérents. Pas de publication dans ce lot.

Recette locale : validation confirmée, refus sans confirmation/auteur, refus de
modification d'un rapport validé, isolation mission, conservation après reprise,
conflit concurrent, migration additive. SSO réel et droits multi-équipiers :
NON VÉRIFIÉS.

## Décision d'intégration MCP

Le 20 octobre 2026, le propriétaire retire explicitement les règles projet
ARCenal Agent Link. L'obligation d'un connecteur central préexistant et le
parcours d'assistance imposé ne constituent plus des exigences du projet.

La cible demandée est un serveur MCP intégré à ARCenal Report, installé dans
YunoHost. Hermes en sera le client. L'URL HTTPS et l'authentification seront
fournies après implémentation et configuration réelles, sans endpoint fictif
annoncé disponible. Les protections de sécurité ci-dessous sont maintenues.

## Objectif et utilisateurs

L’équipier consigne ses observations ; le responsable relit et valide les
livrables ; le client reçoit uniquement les documents explicitement approuvés.
ARCenal Report conserve les sources de référence. Proposition : Hermes analyse
les seules données autorisées nécessaires, sans devenir un second registre.

## Périmètre proposé

1. Regrouper notes, transcriptions validées, photos jointes et météo par mission
   et journée. Conserver auteur, heure de survenue, heure de saisie et fuseau.
2. Préparer sur demande un brouillon quotidien : orthographe, grammaire,
   syntaxe, vocabulaire et regroupement des redites sans perte de faits distincts.
3. Rendre le texte modifiable ; validation humaine avant enregistrement du
   résultat Hermes et avant export ou transmission. Proposer un export Word
   quotidien ; aucun envoi automatique au client dans ce premier lot.
4. Lot ultérieur : REX détaillé à partir des rapports validés, avec chronologie,
   résultats, difficultés, enseignements et recommandations clairement séparées
   des faits, et références aux journées et sources concernées.

## Fiabilité et confidentialité

Ne pas modifier les originaux. Conserver séparément texte source, proposition,
corrections humaines et version validée. Ne pas inventer de cause, mesure,
diagnostic, action ou conclusion technique ; signaler les ambiguïtés à vérifier.
Une transcription ou une photo seule ne prouve pas un constat technique.
Ne pas analyser les images ni envoyer leurs fichiers par défaut.
Vérifier l’hébergement du modèle et les destinataires des données avant tout
transfert, même si Hermes lui-même est auto-hébergé.

## Protections du futur connecteur

Authentification dédiée et révocable, moindre privilège et vérification des
missions autorisées côté serveur. Aucun secret dans l'URL, le dépôt, le stockage
local du navigateur ou les journaux client. Premier périmètre en lecture seule ;
les écritures éventuelles devront être spécifiées et autorisées séparément.
La validation finale d'un rapport appartient toujours à un équipier dans
l'application, jamais à Hermes. La suppression de la règle d'architecture
n'autorise ni l'accès anonyme aux données ni une diffusion automatique.

## Critères de recette

- AC-01 : sélection d’une journée dans le fuseau de mission, sans mélange avec
  une autre mission, avec accès limité aux équipiers autorisés.
- AC-02 : chaque fait du brouillon peut être relié à une entrée source ; auteur,
  dates, chiffres et unités restent fidèles ou sont signalés pour vérification.
- AC-03 : deux événements similaires distincts ne disparaissent pas lors de la
  suppression des redites ; les contradictions restent visibles à la relecture.
- AC-04 : original inchangé, brouillon éditable, version validée identifiable,
  export Word correspondant au texte approuvé, sans diffusion implicite.
- AC-05 : refus des accès sans authentification, avec authentification invalide
  ou révoquée et aux missions non autorisées ; aucun secret dans URL et journaux.
- AC-06 : premier connecteur MCP en lecture seule, refus des opérations
  d'écriture ; validation finale des rapports uniquement par un équipier.
- AC-07 : indisponibilité Hermes = conservation des entrées et accès au rapport
  factuel local, avec un message explicite et possibilité de réessayer.
- AC-08 (lot REX) : seules les versions validées alimentent le REX ; références
  vérifiables et validation humaine avant remise au client.

## Existant vérifié et limites

Le dépôt enregistre déjà des entrées et rapports horodatés et propose un export
DOCX. La route de génération appelle actuellement le rapport factuel local,
pas Hermes. Le module Ollama présent ne constitue pas un connecteur Hermes.
Connecteur MCP Report sur YunoHost et recette de bout en bout : À RÉALISER.
Le lot validation/historique existe dans le code local avec tests, mais sa revue
finale, sa recette navigateur et sa recette YunoHost restent à terminer.

Le dépôt Hermes identifié est https://github.com/arcenal-coder/arcenal-agent.
L'existence de son API d'agents ne constitue pas une preuve d'un serveur MCP
Report déployé. Prochaine étape : spécifier les outils en lecture seule et
l'authentification du connecteur Report, puis vérifier le packaging YunoHost.
