const integrationBase = new URL('api/v1/integrations', document.baseURI).pathname;
const integrationError = document.querySelector('#integration-error');
const integrationStatus = document.querySelector('#integration-status');
const secretInput = document.querySelector('#new-token');
const secretSection = document.querySelector('#credential-secret');
let integrationConfiguration;

async function integrationRequest(suffix = '', payload) {
  const response = await fetch(integrationBase + suffix, {
    method:payload === undefined ? 'GET' : 'POST', credentials:'same-origin', cache:'no-store',
    headers:{'Content-Type':'application/json'}, body:payload === undefined ? undefined : JSON.stringify(payload)
  });
  if (!response.headers.get('Content-Type')?.includes('application/json')) throw new Error('Connexion administrateur YunoHost requise.');
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Action impossible.');
  return body;
}

function forgetSecret() {
  secretInput.value = ''; secretInput.type = 'password'; secretSection.hidden = true;
}

async function loadIntegrations() {
  integrationConfiguration = await integrationRequest();
  document.querySelector('#mcp-url').textContent = integrationConfiguration.mcp_url;
  document.querySelector('#rest-url').textContent = integrationConfiguration.api_url;
  const missionContainer = document.querySelector('#credential-missions');
  missionContainer.replaceChildren();
  integrationConfiguration.missions.forEach(mission => {
    const label = document.createElement('label');
    const input = document.createElement('input'); input.type = 'checkbox'; input.name = 'mission'; input.value = mission.uuid;
    label.append(input, document.createTextNode(` ${mission.reference} — ${mission.title}`)); missionContainer.append(label);
  });
  const container = document.querySelector('#credentials-list'); container.replaceChildren();
  integrationConfiguration.credentials.forEach(credential => {
    const row = document.createElement('article'); row.className = 'integration-credential';
    const title = document.createElement('h3'); title.textContent = credential.label;
    const active = !credential.revoked_at && credential.expires_at * 1000 > Date.now();
    const details = document.createElement('p');
    details.textContent = `${credential.revoked_at ? 'Révoqué' : active ? 'Actif' : 'Expiré'} · ${credential.missions.length} mission(s) · ${credential.scopes.join(', ')} · expiration ${new Date(credential.expires_at * 1000).toLocaleString('fr-FR')}`;
    row.append(title, details);
    if (active) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'secondary-button'; button.textContent = 'Révoquer cet accès';
      button.addEventListener('click', async () => {
        if (!window.confirm(`Révoquer l’accès « ${credential.label} » ? Hermes ne pourra plus l’utiliser. Les rapports seront conservés.`)) return;
        integrationError.textContent = ''; button.disabled = true;
        try {
          await integrationRequest(`/credentials/${credential.uuid}/revoke`, {confirmed:true});
          forgetSecret(); await loadIntegrations(); integrationStatus.textContent = 'Accès révoqué.';
        } catch (error) { integrationError.textContent = error.message; button.disabled = false; }
      });
      row.append(button);
    }
    container.append(row);
  });
  if (!integrationConfiguration.credentials.length) container.textContent = 'Aucun accès créé. Le MCP refuse toute requête sans jeton valide.';
  integrationStatus.textContent = 'Configuration chargée. Aucun échange avec Hermes n’est déclenché par cet écran.';
}

document.querySelector('#credential-form').addEventListener('submit', async event => {
  event.preventDefault(); integrationError.textContent = '';
  const label = document.querySelector('#credential-label').value.trim();
  const missions = [...document.querySelectorAll('input[name="mission"]:checked')].map(input => input.value);
  const scopes = [...document.querySelectorAll('input[name="scope"]:checked')].map(input => input.value);
  const references = integrationConfiguration.missions.filter(mission => missions.includes(mission.uuid)).map(mission => mission.reference);
  if (!missions.length || !scopes.length) { integrationError.textContent = 'Sélectionnez au moins une mission et une portée.'; return; }
  if (!window.confirm(`Créer l’accès « ${label} » pour ${references.join(', ')} avec les portées ${scopes.join(', ')} ? Le détenteur du jeton pourra lire ces données jusqu’à expiration ou révocation.`)) return;
  const button = document.querySelector('#create-credential'); button.disabled = true; forgetSecret();
  try {
    const created = await integrationRequest('/credentials', {label, missions, scopes, expires_days:Number(document.querySelector('#expiry-days').value), confirmed:true});
    secretInput.value = created.token; secretSection.hidden = false;
    await loadIntegrations(); secretInput.focus();
    integrationStatus.textContent = 'Accès créé. Copiez le jeton dans le coffre de Hermes ; il ne sera pas réaffiché.';
  } catch (error) { integrationError.textContent = error.message; }
  finally { button.disabled = false; }
});
document.querySelector('#toggle-token').addEventListener('click', () => { secretInput.type = secretInput.type === 'password' ? 'text' : 'password'; });
document.querySelector('#forget-token').addEventListener('click', forgetSecret);
window.addEventListener('pagehide', forgetSecret);
loadIntegrations().catch(error => { integrationStatus.textContent = ''; integrationError.textContent = error.message; });
