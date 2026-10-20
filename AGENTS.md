# BEGIN ARCENAL DEV HARNESS
Use ARCenal skills for ARCenal/YunoHost work. Preserve the Noob guidance and human confirmation rules from the installed skills.
# END ARCENAL DEV HARNESS

## Décision du propriétaire — 20 octobre 2026

Le bloc de règles projet « ARCENAL AGENT LINK » fourni précédemment est retiré
à la demande explicite du propriétaire. Ses contraintes d'architecture ne
s'appliquent plus comme exigences propres à ARCenal Report : ni obligation de
passer exclusivement par un connecteur central, ni interdiction projet d'un
serveur MCP intégré à l'application, ni parcours d'assistance SSO imposé.

Le besoin est un serveur MCP intégré au paquet ARCenal Report installé dans
YunoHost, auquel Hermes pourra se connecter. Ce n'est pas un serveur MCP à
lancer sur le Mac de développement. L'URL et l'authentification ne doivent être
annoncées opérationnelles qu'après déploiement et vérification.

Conserver les protections indépendantes de cette ancienne règle : secrets hors
du dépôt et des URL, authentification et autorisations vérifiées côté serveur,
moindre privilège, validation humaine des rapports, conservation des originaux
et des versions validées. Pas de publication ni de déploiement implicite.
