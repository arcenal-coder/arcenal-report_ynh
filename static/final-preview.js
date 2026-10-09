const screens = document.querySelectorAll('.screen');

function showScreen(id) {
  screens.forEach(screen => screen.classList.toggle('active', screen.id === id));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelectorAll('[data-screen]').forEach(button => {
  button.addEventListener('click', () => showScreen(button.dataset.screen));
});

document.querySelectorAll('[data-demo-message]').forEach(button => {
  button.addEventListener('click', () => {
    const hint = document.querySelector('.screen.active .hint');
    if (hint) hint.textContent = 'Action illustrative : cette fonction sera développée dans une étape ultérieure.';
  });
});
