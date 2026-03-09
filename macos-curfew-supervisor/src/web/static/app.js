const token = window.CURFEW_CONTEXT.token;
let deadlineIso = window.CURFEW_CONTEXT.deadline;

function pad(n) {
  return String(n).padStart(2, '0');
}

function renderCountdown() {
  const now = new Date();
  const deadline = new Date(deadlineIso);
  const diffMs = deadline - now;
  const el = document.getElementById('countdown');
  if (diffMs <= 0) {
    el.textContent = '00:00';
    return;
  }
  const totalSec = Math.floor(diffMs / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  el.textContent = `${pad(min)}:${pad(sec)}`;
}

async function refreshStatus() {
  const res = await fetch(`/status?token=${encodeURIComponent(token)}`);
  if (!res.ok) {
    return;
  }
  const data = await res.json();
  deadlineIso = data.deadline;
  document.getElementById('deadline').textContent = new Date(deadlineIso).toLocaleString();
}

async function submitOverride(code) {
  const res = await fetch('/override', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, code })
  });

  const status = document.getElementById('status');
  const data = await res.json().catch(() => ({}));

  if (res.ok && data.ok) {
    status.textContent = `Override accepted. New deadline: ${new Date(data.deadline).toLocaleString()}`;
    status.style.color = '#86efac';
    deadlineIso = data.deadline;
    document.getElementById('code').value = '';
    return;
  }

  status.textContent = `Override failed: ${data.error || 'unknown_error'}`;
  status.style.color = '#fca5a5';
}

document.getElementById('override-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const code = document.getElementById('code').value.trim().toUpperCase();
  if (!code) return;
  await submitOverride(code);
});

setInterval(renderCountdown, 1000);
setInterval(refreshStatus, 10000);
renderCountdown();
refreshStatus();
