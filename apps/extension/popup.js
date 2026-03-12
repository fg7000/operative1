// Operative1 Twitter Cookie Capture
const API_URL = 'https://keen-mindfulness-production-970b.up.railway.app';

document.addEventListener('DOMContentLoaded', () => {
  const connectSection = document.getElementById('connect-section');
  const successSection = document.getElementById('success-section');
  const errorSection = document.getElementById('error-section');
  const loginPrompt = document.getElementById('login-prompt');
  const statusSection = document.getElementById('status-section');
  const statusMessage = document.getElementById('status-message');
  const errorMessage = document.getElementById('error-message');
  const connectBtn = document.getElementById('connect-btn');
  const retryBtn = document.getElementById('retry-btn');
  const emailInput = document.getElementById('email-input');

  function showSection(section) {
    [connectSection, successSection, errorSection, loginPrompt].forEach(s => s.classList.add('hidden'));
    section.classList.remove('hidden');
  }

  function showStatus(msg) {
    statusSection.classList.remove('hidden');
    statusMessage.textContent = msg;
  }

  function hideStatus() {
    statusSection.classList.add('hidden');
  }

  function showError(msg) {
    errorMessage.textContent = msg;
    showSection(errorSection);
  }

  async function getTwitterCookies() {
    return new Promise((resolve) => {
      const cookies = {};
      let pending = 2;

      function checkDone() {
        pending--;
        if (pending === 0) {
          resolve(cookies.auth_token && cookies.ct0 ? cookies : null);
        }
      }

      chrome.cookies.get({ url: 'https://x.com', name: 'auth_token' }, (cookie) => {
        if (cookie) cookies.auth_token = cookie.value;
        checkDone();
      });

      chrome.cookies.get({ url: 'https://x.com', name: 'ct0' }, (cookie) => {
        if (cookie) cookies.ct0 = cookie.value;
        checkDone();
      });
    });
  }

  async function sendCookiesToBackend(email, cookies) {
    const response = await fetch(`${API_URL}/settings/twitter-cookies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: email,
        auth_token: cookies.auth_token,
        ct0: cookies.ct0
      })
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Server error: ${response.status}`);
    }

    return response.json();
  }

  connectBtn.addEventListener('click', async () => {
    const email = emailInput.value.trim();
    if (!email || !email.includes('@')) {
      showError('Please enter a valid email address');
      return;
    }

    showStatus('Checking Twitter login...');
    connectBtn.disabled = true;

    try {
      const cookies = await getTwitterCookies();

      if (!cookies) {
        hideStatus();
        showSection(loginPrompt);
        connectBtn.disabled = false;
        return;
      }

      showStatus('Connecting to Operative1...');

      await sendCookiesToBackend(email, cookies);
      hideStatus();
      showSection(successSection);

    } catch (err) {
      hideStatus();
      showError(err.message || 'Connection failed. Please try again.');
      connectBtn.disabled = false;
    }
  });

  retryBtn.addEventListener('click', () => {
    showSection(connectSection);
    connectBtn.disabled = false;
  });
});
