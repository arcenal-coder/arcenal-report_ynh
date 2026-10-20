const missionsView = document.querySelector('#missions-view');
const missionView = document.querySelector('#mission-view');
const missionsContainer = document.querySelector('#missions');
let currentMission;
// document.baseURI preserves the YunoHost installation path (for example
// /arcenal-report/) while also working when the application is served at /.
const apiBase = new URL('api/v1/', document.baseURI).pathname.replace(/\/$/, '');
const apiUrl = path => `${apiBase}${path}`;

function locateForWeather() {
  return new Promise(resolve => {
    if (!navigator.geolocation) { resolve(null); return; }
    navigator.geolocation.getCurrentPosition(
      position => resolve({latitude: Math.round(position.coords.latitude * 100) / 100, longitude: Math.round(position.coords.longitude * 100) / 100}),
      () => resolve(null), {timeout:10000, maximumAge:600000, enableHighAccuracy:false}
    );
  });

}

function formatTime(timestamp) { return new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' }).format(new Date(timestamp)); }
function escapeHtml(value) { const node = document.createElement('div'); node.textContent = value; return node.innerHTML; }

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => null);
  if (!response.ok || body === null) {
    const error = new Error(response.status === 401 || (response.redirected && body === null)
      ? 'Votre session a expiré. Reconnectez-vous à YunoHost.'
      : body?.error || `Le service ne répond pas correctement (HTTP ${response.status}). Réessayez.`);
    error.status = response.redirected && body === null ? 401 : response.status;
    throw error;
  }
  return body;
}

function showMissionLoadError(error) {
  document.querySelector('#missions-load-error').hidden = false;
  document.querySelector('#missions-error-message').textContent = error.message || 'Service inaccessible. Vérifiez votre connexion puis réessayez.';
  document.querySelector('#missions-login').hidden = error.status !== 401;
}

async function loadMissions() {
  missionView.hidden = true; missionsView.hidden = false;
  document.querySelector('#missions-load-error').hidden = true;
  const button = document.querySelector('#retry-missions');
  button.disabled = true;
  try { await showMissions(); }
  catch (error) { showMissionLoadError(error); }
  finally { button.disabled = false; }
}

async function showMissions() {
  const { missions } = await fetchJson(apiUrl('/missions'));
  missionsContainer.innerHTML = missions.map(mission => `<button class="mission-card" type="button" data-mission="${mission.uuid}"><strong>${escapeHtml(mission.client_name)}</strong><span class="title">${escapeHtml(mission.title)}</span><footer><span><i class="status-dot"></i>En cours</span><span>Ouvrir →</span></footer></button>`).join('');
  if (!missions.length) missionsContainer.textContent = 'Aucune mission pour le moment. Créez votre première mission pour commencer les saisies.';
  missionsContainer.querySelectorAll('[data-mission]').forEach(button => button.addEventListener('click', () => showMission(button.dataset.mission).catch(showMissionLoadError)));
  missionView.hidden = true; missionsView.hidden = false;
}

function renderEntry(entry) {
  if (entry.entry_type === 'photo') {
    return `<article class="entry"><time>${formatTime(entry.occurred_at)}</time><div><span class="entry-label">📷 ${escapeHtml(entry.original_name)}</span><img class="entry-photo" src="${apiUrl(`/entries/${entry.uuid}/file`)}" alt="${escapeHtml(entry.original_name)}" loading="lazy"></div></article>`;
  }
  if (entry.entry_type === 'audio') {
    const status = entry.transcription_status || 'not_requested';
    const messages = { queued:'Transcription en attente…', processing:'Transcription en cours…', unavailable:'Transcription locale à configurer.', failed:'Transcription à relancer.' };
    const transcript = entry.transcript ? `<p class="transcript">${escapeHtml(entry.transcript)}</p>` : '';
    const retry = ['failed', 'unavailable', 'not_requested'].includes(status) ? `<button class="transcribe-button" type="button" data-transcribe="${entry.uuid}">${status === 'not_requested' ? 'Transcrire cet enregistrement' : 'Relancer la transcription'}</button>` : '';
    const diagnostic = entry.transcription_error ? `<p class="form-error" role="alert">${escapeHtml(entry.transcription_error)}</p>` : '';
    return `<article class="entry"><time>${formatTime(entry.occurred_at)}</time><div><span class="entry-label">🎙 Note vocale</span><audio class="entry-audio" controls preload="metadata" src="${apiUrl(`/entries/${entry.uuid}/file`)}"></audio><p class="transcription-status ${status}">${status === 'completed' ? 'Transcription terminée' : messages[status] || ''}</p>${diagnostic}${transcript}${retry}</div></article>`;
  }
  return `<article class="entry"><time>${formatTime(entry.occurred_at)}</time><p>${escapeHtml(entry.content)}</p></article>`;
}

function renderEntries(entries) {
  document.querySelector('#entries').innerHTML = entries.length ? entries.map(renderEntry).join('') : '<p>Aucune information enregistrée.</p>';
  document.querySelectorAll('[data-transcribe]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await fetchJson(apiUrl(`/entries/${button.dataset.transcribe}/transcribe`), { method: 'POST' });
      await showMission(currentMission.uuid);
    } catch (error) {
      button.disabled = false;
      const message = document.createElement('p'); message.className = 'form-error'; message.setAttribute('role', 'alert'); message.textContent = error.message; button.after(message);
    }
  }));
}

function setupAudioRecorder(uuid, audioForm) {
  const startButton = audioForm.querySelector('#start-recording');
  const stopButton = audioForm.querySelector('#stop-recording');
  const saveButton = audioForm.querySelector('#save-audio');
  const fileInput = audioForm.querySelector('#audio-file');
  const preview = audioForm.querySelector('#recording-preview');
  const status = audioForm.querySelector('#recording-status');
  const error = audioForm.querySelector('#audio-error');
  let recorder;
  let recordedBlob;
  let previewUrl;
  let cancelled = false;

  function setPreview(blob) {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    preview.src = previewUrl;
    preview.hidden = false;
    saveButton.disabled = false;
    status.textContent = 'Enregistrement prêt à être réécouté';
    status.className = 'recording-status ready';
  }

  function stopStream() {
    if (recorder?.stream) recorder.stream.getTracks().forEach(track => track.stop());
  }

  startButton.addEventListener('click', async () => {
    error.textContent = '';
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      error.textContent = 'Le dictaphone n’est pas pris en charge par ce navigateur. Utilisez le choix de fichier audio.';
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      cancelled = false;
      const preferredTypes = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg;codecs=opus'];
      const mimeType = preferredTypes.find(type => MediaRecorder.isTypeSupported(type));
      recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      const chunks = [];
      recorder.addEventListener('dataavailable', event => { if (event.data.size) chunks.push(event.data); });
      recorder.addEventListener('stop', () => {
        recordedBlob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        stopStream();
        if (!cancelled) setPreview(recordedBlob);
      });
      recorder.start();
      startButton.disabled = true; stopButton.disabled = false; saveButton.disabled = true;
      status.textContent = 'Enregistrement en cours…'; status.className = 'recording-status active';
    } catch (exception) {
      error.textContent = 'Le microphone n’est pas accessible. Vérifiez l’autorisation du navigateur.';
    }
  });

  stopButton.addEventListener('click', () => {
    if (recorder?.state === 'recording') recorder.stop();
    startButton.disabled = false; stopButton.disabled = true;
  });

  fileInput.addEventListener('change', () => {
    recordedBlob = undefined;
    if (fileInput.files[0]) setPreview(fileInput.files[0]);
  });

  audioForm.querySelector('#cancel-audio').addEventListener('click', () => {
    cancelled = true;
    if (recorder?.state === 'recording') recorder.stop(); else stopStream();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    audioForm.reset(); audioForm.hidden = true;
  });

  audioForm.addEventListener('submit', async event => {
    event.preventDefault(); error.textContent = ''; saveButton.disabled = true;
    const audio = recordedBlob || fileInput.files[0];
    if (!audio) { error.textContent = 'Enregistrez ou choisissez d’abord un fichier audio.'; return; }
    const extension = audio.type.includes('mp4') ? 'm4a' : audio.type.includes('ogg') ? 'ogg' : audio.type.includes('mpeg') ? 'mp3' : audio.type.includes('wav') ? 'wav' : 'webm';
    const formData = new FormData();
    formData.append('audio', audio, fileInput.files[0]?.name || `note-vocale.${extension}`);
    try { await fetchJson(apiUrl(`/missions/${uuid}/audio`), { method:'POST', body:formData }); await showMission(uuid); }
    catch (exception) { error.textContent = exception.message; saveButton.disabled = false; }
  });
}

async function showMission(uuid) {
  currentMission = await fetchJson(apiUrl(`/missions/${uuid}`));
  const fragment = document.querySelector('#mission-template').content.cloneNode(true);
  missionView.replaceChildren(fragment);
  missionView.querySelector('#client-name').textContent = currentMission.client_name;
  missionView.querySelector('#mission-title').textContent = currentMission.title;
  missionView.querySelector('#mission-reference').textContent = currentMission.reference;
  const { entries } = await fetchJson(apiUrl(`/missions/${uuid}/entries`)); renderEntries(entries);
  if (entries.some(entry => entry.entry_type === 'audio' && ['queued', 'processing'].includes(entry.transcription_status))) window.setTimeout(() => showMission(uuid), 2500);
  missionView.querySelectorAll('[data-home]').forEach(button => button.addEventListener('click', loadMissions));
  const options = missionView.querySelector('#add-options');
  const form = missionView.querySelector('#entry-form');
  const photoForm = missionView.querySelector('#photo-form');
  const audioForm = missionView.querySelector('#audio-form');
  missionView.querySelector('#add-text').addEventListener('click', () => { form.hidden = false; missionView.querySelector('#entry-content').focus(); });
  missionView.querySelector('#add-photo').addEventListener('click', () => { photoForm.hidden = false; });
  missionView.querySelector('#add-audio').addEventListener('click', () => { audioForm.hidden = false; });
  missionView.querySelector('#cancel-entry').addEventListener('click', () => { form.reset(); form.hidden = true; });
  missionView.querySelector('#cancel-photo').addEventListener('click', () => { photoForm.reset(); photoForm.hidden = true; });
  const reportPreview = missionView.querySelector('#report-preview');
  const reportContent = missionView.querySelector('#report-content');
  const reportError = missionView.querySelector('#report-error');
  const reportMode = missionView.querySelector('#report-mode');
  let report;
  let hermesAvailable = false;
  let hermesProposal;
  const authorInput = missionView.querySelector('#report-author');
  authorInput.value = localStorage.getItem('arcenal-report-author') || '';
  const validationStatus = missionView.querySelector('#report-validation-status');
  function displayReport(value) {
    report = value;
    const validated = report.status === 'validated';
    reportContent.value = report.content;
    reportContent.readOnly = validated;
    reportMode.textContent = validated ? `Version ${report.validation.version} validée` : 'Brouillon modifiable';
    validationStatus.textContent = validated
      ? `Validé par ${report.validation.validated_by} le ${new Date(report.validation.validated_at).toLocaleString('fr-FR')}. Consultation figée.${report.validation.identity_source === 'local_declared' ? ' Identité déclarative — POC local.' : ''}`
      : `Relisez et enregistrez vos corrections avant de valider. ${hermesAvailable ? 'Correction avec Hermes disponible sur demande.' : 'Aucune connexion Hermes autorisée sur cette mission.'}`;
    missionView.querySelector('#save-report').hidden = validated;
    missionView.querySelector('#validate-report').hidden = validated;
    missionView.querySelector('#reopen-report').hidden = !validated;
    missionView.querySelector('#hermes-corrections').hidden = validated || !hermesAvailable;
    missionView.querySelector('#hermes-proposal-section').hidden = true;
    hermesProposal = null;
    reportPreview.hidden = false;
  }
  async function persistDraft() {
    if (report?.status === 'validated') return;
    displayReport(await fetchJson(apiUrl(`/missions/${uuid}/report`), {
      method:'PUT', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({uuid:report?.uuid, content:reportContent.value, expected_updated_at:report?.updated_at})
    }));
  }
  async function loadHistory() {
    const { versions } = await fetchJson(apiUrl(`/missions/${uuid}/report/versions`));
    const container = missionView.querySelector('#report-versions');
    container.replaceChildren();
    if (!versions.length) { container.textContent = 'Aucun rapport validé.'; return; }
    versions.forEach(version => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'secondary-button';
      button.textContent = `Consulter v${version.version} — ${version.validated_by} — ${new Date(version.validated_at).toLocaleString('fr-FR')}`;
      button.addEventListener('click', async () => {
        reportError.textContent = '';
        if (report?.status === 'draft' && reportContent.value !== report.content && !window.confirm('Les corrections non enregistrées seront perdues. Consulter cette version ?')) return;
        try {
          const saved = await fetchJson(apiUrl(`/missions/${uuid}/report/versions/${version.uuid}`));
          displayReport({...saved, uuid:saved.report_uuid, status:'validated', validation:{...version}});
        } catch (error) { reportError.textContent = error.message; }
      });
      container.append(button);
    });
  }
  const latest = await fetchJson(apiUrl(`/missions/${uuid}/report`));
  try { hermesAvailable = (await fetchJson(apiUrl(`/missions/${uuid}/report/assist`))).available; }
  catch { hermesAvailable = false; }
  if (hermesAvailable) missionView.querySelector('#agent-unavailable').textContent = 'Correction Hermes configurée pour cette mission. Chaque envoi et chaque application de correction nécessitent votre confirmation. Le MCP reste une connexion distincte en lecture seule.';
  if (latest.report) displayReport(latest.report);
  await loadHistory();
  missionView.querySelector('#generate-report').addEventListener('click', async () => {
    reportError.textContent = '';
    if (!authorInput.value.trim()) { authorInput.focus(); authorInput.reportValidity(); authorInput.setCustomValidity('Renseignez le nom de l’équipier.'); authorInput.reportValidity(); return; }
    authorInput.setCustomValidity('');
    localStorage.setItem('arcenal-report-author', authorInput.value.trim());
    const generateButton = missionView.querySelector('#generate-report');
    const weatherStatus = missionView.querySelector('#weather-status');
    generateButton.disabled = true;
    try {
      weatherStatus.textContent = 'Localisation pour la météo…';
      const location = await locateForWeather();
      weatherStatus.textContent = location ? 'Récupération des prévisions météo…' : 'Localisation indisponible : le rapport sera généré sans météo.';
      report = await fetchJson(apiUrl(`/missions/${uuid}/report`), { method: 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({author:authorInput.value.trim(), location}) });
      displayReport(report);
      weatherStatus.textContent = 'Rapport généré. Consultez la rubrique météo du rapport.';
      reportContent.focus();
    } catch (exception) { reportError.textContent = exception.message; reportPreview.hidden = false; }
    finally { generateButton.disabled = false; }
  });
  missionView.querySelector('#save-report').addEventListener('click', async () => {
    reportError.textContent = '';
    try {
      await persistDraft();
      validationStatus.textContent = 'Brouillon enregistré. Relisez-le avant validation.';
    } catch (exception) { reportError.textContent = exception.message; }
  });
  missionView.querySelector('#validate-report').addEventListener('click', async () => {
    reportError.textContent = '';
    if (!report || report.status === 'validated') return;
    if (!authorInput.value.trim()) { reportError.textContent = 'Renseignez le nom de l’équipier qui valide.'; authorInput.focus(); return; }
    if (reportContent.value !== report.content) { reportError.textContent = 'Enregistrez vos corrections, puis relisez le texte avant de valider.'; return; }
    if (!window.confirm(`Valider le rapport de la mission ${currentMission.reference} au nom de ${authorInput.value.trim()} (ou de votre identité SSO) ? Le texte affiché sera figé et archivé. Toute correction créera ensuite une nouvelle version. Aucun envoi au client.`)) return;
    const button = missionView.querySelector('#validate-report'); button.disabled = true;
    try {
      displayReport(await fetchJson(apiUrl(`/missions/${uuid}/report/validate`), {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({uuid:report.uuid, content:report.content, expected_updated_at:report.updated_at,
          author:authorInput.value.trim(), confirmed:true})
      }));
      await loadHistory();
    } catch (error) { reportError.textContent = error.message; }
    finally { button.disabled = false; }
  });
  missionView.querySelector('#reopen-report').addEventListener('click', async () => {
    reportError.textContent = '';
    if (!report?.validation) return;
    const reason = window.prompt(`Motif de reprise de la version ${report.validation.version} (500 caractères maximum). L’original restera inchangé.`);
    if (reason === null) return;
    try {
      displayReport(await fetchJson(apiUrl(`/missions/${uuid}/report/versions/${report.validation.uuid}/reopen`), {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({reason, confirmed:true})
      }));
      reportContent.focus();
    } catch (error) { reportError.textContent = error.message; }
  });
  missionView.querySelector('#print-report').addEventListener('click', () => window.print());
  missionView.querySelector('#hermes-request').addEventListener('click', async () => {
    reportError.textContent = '';
    const instruction = missionView.querySelector('#hermes-instruction').value.trim();
    if (!report || report.status !== 'draft' || !instruction) { reportError.textContent = 'Ouvrez un brouillon et précisez la correction souhaitée.'; return; }
    if (reportContent.value !== report.content) { reportError.textContent = 'Enregistrez vos corrections avant de demander une proposition.'; return; }
    if (!window.confirm(`Transmettre le brouillon de ${currentMission.reference} et votre demande à l’agent Report de Hermes, avec votre identité connectée ? Le fournisseur IA configuré côté Hermes traitera ce texte. Aucun fichier audio/photo ne sera envoyé.`)) return;
    const button = missionView.querySelector('#hermes-request'); button.disabled = true;
    const status = missionView.querySelector('#hermes-status'); status.textContent = 'Proposition en cours… Le brouillon reste inchangé.';
    const source = {...report};
    try {
      const proposal = await fetchJson(apiUrl(`/missions/${uuid}/report/assist`), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({uuid:source.uuid, expected_updated_at:source.updated_at, instruction, confirmed:true})});
      if (report?.uuid !== source.uuid || report.updated_at !== source.updated_at || reportContent.value !== source.content) throw new Error('Le brouillon affiché a changé. Redemandez une proposition.');
      hermesProposal = {...proposal, sourceContent:source.content};
      missionView.querySelector('#hermes-proposal').value = proposal.content;
      missionView.querySelector('#hermes-proposal-section').hidden = false;
      status.textContent = 'Proposition reçue : relisez-la avant de l’appliquer. Elle ne vaut pas validation technique.';
    } catch (error) { reportError.textContent = error.message; status.textContent = 'Aucune correction appliquée.'; }
    finally { button.disabled = false; }
  });
  missionView.querySelector('#hermes-apply').addEventListener('click', async () => {
    reportError.textContent = '';
    if (!hermesProposal || report?.status !== 'draft' || report.uuid !== hermesProposal.uuid || report.updated_at !== hermesProposal.expected_updated_at || reportContent.value !== hermesProposal.sourceContent) { reportError.textContent = 'Brouillon modifié : redemandez une proposition.'; return; }
    if (!window.confirm('Remplacer le texte du brouillon par la proposition affichée ? Le rapport restera à relire et à valider séparément.')) return;
    try {
      displayReport(await fetchJson(apiUrl(`/missions/${uuid}/report`), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({uuid:hermesProposal.uuid, content:hermesProposal.content, expected_updated_at:hermesProposal.expected_updated_at})}));
      missionView.querySelector('#hermes-status').textContent = 'Correction enregistrée dans le brouillon. Vous pouvez demander une autre correction ou relire et valider.';
    } catch (error) { reportError.textContent = error.message; }
  });
  authorInput.addEventListener('input', () => authorInput.setCustomValidity(''));
  missionView.querySelector('#email-report').addEventListener('click', () => {
    const subject = `ONYX — Rapport de journée — ${currentMission.reference}`;
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(reportContent.value)}`;
  });
  missionView.querySelector('#download-report').addEventListener('click', async () => {
    const button = missionView.querySelector('#download-report');
    button.disabled = true; reportError.textContent = '';
    try {
      await persistDraft();
      const path = report?.validation ? `/missions/${uuid}/report/versions/${report.validation.uuid}/docx` : `/missions/${uuid}/report/${report.uuid}/docx`;
      const response = await fetch(apiUrl(path));
      if (!response.ok) throw new Error((await response.json()).error);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = `rapport-ONYX-${currentMission.reference}.docx`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (exception) { reportError.textContent = exception.message; }
    finally { button.disabled = false; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault(); const content = missionView.querySelector('#entry-content').value; const error = missionView.querySelector('#form-error'); error.textContent = '';
    try { await fetchJson(apiUrl(`/missions/${uuid}/entries`), { method:'POST', headers:{ 'Content-Type':'application/json' }, body:JSON.stringify({ content }) }); await showMission(uuid); }
    catch (exception) { error.textContent = exception.message; }
  });
  photoForm.addEventListener('submit', async event => {
    event.preventDefault();
    const error = missionView.querySelector('#photo-error');
    const submitButton = photoForm.querySelector('[type="submit"]');
    error.textContent = ''; submitButton.disabled = true;
    try { await fetchJson(apiUrl(`/missions/${uuid}/photos`), { method:'POST', body:new FormData(photoForm) }); await showMission(uuid); }
    catch (exception) { error.textContent = exception.message; submitButton.disabled = false; }
  });
  setupAudioRecorder(uuid, audioForm);
  missionsView.hidden = true; missionView.hidden = false;
}

document.querySelectorAll('header [data-home]').forEach(button => button.addEventListener('click', loadMissions));
document.querySelector('#retry-missions').addEventListener('click', loadMissions);
const missionCreateForm = document.querySelector('#mission-create-form');
const newMissionButton = document.querySelector('#new-mission');
function closeMissionForm() {
  missionCreateForm.reset(); missionCreateForm.hidden = true;
  newMissionButton.setAttribute('aria-expanded', 'false'); newMissionButton.focus();
}
newMissionButton.addEventListener('click', () => {
  missionCreateForm.hidden = false; newMissionButton.setAttribute('aria-expanded', 'true');
  document.querySelector('#mission-create-error').textContent = '';
  if (!document.querySelector('#mission-date').value) {
    const now = new Date();
    document.querySelector('#mission-date').value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  }
  document.querySelector('#mission-client').focus();
});
document.querySelector('#cancel-mission').addEventListener('click', closeMissionForm);
missionCreateForm.addEventListener('submit', async event => {
  event.preventDefault();
  const button = missionCreateForm.querySelector('[type="submit"]');
  const error = document.querySelector('#mission-create-error');
  error.textContent = ''; button.disabled = true;
  try {
    const payload = Object.fromEntries(new FormData(missionCreateForm));
    const mission = await fetchJson(apiUrl('/missions'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    closeMissionForm();
    document.querySelector('#mission-notice').textContent = `Mission « ${mission.title} » enregistrée (${mission.reference}).`;
    try { await showMission(mission.uuid); }
    catch (openError) { await loadMissions(); showMissionLoadError(openError); }
  } catch (exception) { error.textContent = exception.message; }
  finally { button.disabled = false; }
});
loadMissions();
