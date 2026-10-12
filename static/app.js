const missionsView = document.querySelector('#missions-view');
const missionView = document.querySelector('#mission-view');
const missionsContainer = document.querySelector('#missions');
let currentMission;
// document.baseURI preserves the YunoHost installation path (for example
// /arcenal-report/) while also working when the application is served at /.
const apiBase = new URL('api/v1/', document.baseURI).pathname.replace(/\/$/, '');
const apiUrl = path => `${apiBase}${path}`;

function formatTime(timestamp) { return new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' }).format(new Date(timestamp)); }
function escapeHtml(value) { const node = document.createElement('div'); node.textContent = value; return node.innerHTML; }

async function fetchJson(url, options) { const response = await fetch(url, options); const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Une erreur est survenue.'); return body; }

async function showMissions() {
  const { missions } = await fetchJson(apiUrl('/missions'));
  missionsContainer.innerHTML = missions.map(mission => `<button class="mission-card" type="button" data-mission="${mission.uuid}"><strong>${escapeHtml(mission.client_name)}</strong><span class="title">${escapeHtml(mission.title)}</span><footer><span><i class="status-dot"></i>En cours</span><span>Ouvrir →</span></footer></button>`).join('');
  missionsContainer.querySelectorAll('[data-mission]').forEach(button => button.addEventListener('click', () => showMission(button.dataset.mission)));
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
    const retry = status === 'failed' || status === 'unavailable' ? `<button class="transcribe-button" type="button" data-transcribe="${entry.uuid}">Relancer la transcription</button>` : '';
    return `<article class="entry"><time>${formatTime(entry.occurred_at)}</time><div><span class="entry-label">🎙 Note vocale</span><audio class="entry-audio" controls preload="metadata" src="${apiUrl(`/entries/${entry.uuid}/file`)}"></audio><p class="transcription-status ${status}">${status === 'completed' ? 'Transcription terminée' : messages[status] || ''}</p>${transcript}${retry}</div></article>`;
  }
  return `<article class="entry"><time>${formatTime(entry.occurred_at)}</time><p>${escapeHtml(entry.content)}</p></article>`;
}

function renderEntries(entries) {
  document.querySelector('#entries').innerHTML = entries.length ? entries.map(renderEntry).join('') : '<p>Aucune information enregistrée.</p>';
  document.querySelectorAll('[data-transcribe]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    await fetchJson(apiUrl(`/entries/${button.dataset.transcribe}/transcribe`), { method: 'POST' });
    showMission(currentMission.uuid);
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
  missionView.querySelectorAll('[data-home]').forEach(button => button.addEventListener('click', showMissions));
  const options = missionView.querySelector('#add-options');
  const form = missionView.querySelector('#entry-form');
  const photoForm = missionView.querySelector('#photo-form');
  const audioForm = missionView.querySelector('#audio-form');
  missionView.querySelector('#add-entry').addEventListener('click', () => { options.hidden = !options.hidden; });
  missionView.querySelector('#add-text').addEventListener('click', () => { form.hidden = false; options.hidden = true; missionView.querySelector('#entry-content').focus(); });
  missionView.querySelector('#add-photo').addEventListener('click', () => { photoForm.hidden = false; options.hidden = true; });
  missionView.querySelector('#add-audio').addEventListener('click', () => { audioForm.hidden = false; options.hidden = true; });
  missionView.querySelector('#cancel-entry').addEventListener('click', () => { form.reset(); form.hidden = true; });
  missionView.querySelector('#cancel-photo').addEventListener('click', () => { photoForm.reset(); photoForm.hidden = true; });
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

showMissions().catch(() => { missionsContainer.textContent = "Impossible de charger les missions. Réessayez plus tard."; });
