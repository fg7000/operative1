// Operative1 Twitter Cookie Capture with Product Selection
const API_URL = 'https://keen-mindfulness-production-970b.up.railway.app';

document.addEventListener('DOMContentLoaded', () => {
  const connectSection = document.getElementById('connect-section');
  const successSection = document.getElementById('success-section');
  const errorSection = document.getElementById('error-section');
  const loginPrompt = document.getElementById('login-prompt');
  const statusSection = document.getElementById('status-section');
  const productsSection = document.getElementById('products-section');
  const statusMessage = document.getElementById('status-message');
  const errorMessage = document.getElementById('error-message');
  const connectBtn = document.getElementById('connect-btn');
  const loadProductsBtn = document.getElementById('load-products-btn');
  const retryBtn = document.getElementById('retry-btn');
  const errorRetryBtn = document.getElementById('error-retry-btn');
  const connectAnotherBtn = document.getElementById('connect-another-btn');
  const userIdInput = document.getElementById('user-id-input');
  const productSelect = document.getElementById('product-select');
  const connectedProductName = document.getElementById('connected-product-name');

  let loadedProducts = [];

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

  function resetForm() {
    showSection(connectSection);
    productsSection.classList.add('hidden');
    productSelect.innerHTML = '<option value="">-- Select a product --</option>';
    connectBtn.disabled = true;
    loadedProducts = [];
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

  async function loadProducts(userId) {
    const response = await fetch(`${API_URL}/products/by-user/${userId}`);
    if (!response.ok) {
      throw new Error('Failed to load products');
    }
    return response.json();
  }

  async function sendCookiesToBackend(productId, cookies, twitterHandle) {
    const response = await fetch(`${API_URL}/settings/twitter-cookies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_id: productId,
        auth_token: cookies.auth_token,
        ct0: cookies.ct0,
        twitter_handle: twitterHandle || ''
      })
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Server error: ${response.status}`);
    }

    return response.json();
  }

  async function getTwitterHandle(cookies) {
    // Try to get the logged-in user's handle from Twitter
    try {
      const response = await fetch('https://api.twitter.com/1.1/account/verify_credentials.json', {
        headers: {
          'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
          'x-csrf-token': cookies.ct0
        },
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        return data.screen_name;
      }
    } catch (e) {
      // Ignore - we'll just not have the handle
    }
    return '';
  }

  // Load products when user enters ID and clicks button
  loadProductsBtn.addEventListener('click', async () => {
    const userId = userIdInput.value.trim();
    if (!userId || userId.length < 10) {
      showError('Please enter a valid User ID (copy from Settings page)');
      return;
    }

    showStatus('Loading your products...');
    loadProductsBtn.disabled = true;

    try {
      const products = await loadProducts(userId);

      if (!products || products.length === 0) {
        hideStatus();
        showError('No products found. Create a product first in the dashboard.');
        loadProductsBtn.disabled = false;
        return;
      }

      // Populate product dropdown
      productSelect.innerHTML = '<option value="">-- Select a product --</option>';
      products.forEach(p => {
        const option = document.createElement('option');
        option.value = p.id;
        option.textContent = p.name || p.slug;
        productSelect.appendChild(option);
      });

      loadedProducts = products;
      productsSection.classList.remove('hidden');
      hideStatus();
      loadProductsBtn.disabled = false;

      // Auto-select if only one product
      if (products.length === 1) {
        productSelect.value = products[0].id;
        connectBtn.disabled = false;
      }

    } catch (err) {
      hideStatus();
      showError(err.message || 'Failed to load products');
      loadProductsBtn.disabled = false;
    }
  });

  // Enable connect button when product is selected
  productSelect.addEventListener('change', () => {
    connectBtn.disabled = !productSelect.value;
  });

  // Connect Twitter to selected product
  connectBtn.addEventListener('click', async () => {
    const productId = productSelect.value;
    if (!productId) {
      showError('Please select a product');
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

      // Try to get Twitter handle
      const handle = await getTwitterHandle(cookies);

      await sendCookiesToBackend(productId, cookies, handle);

      hideStatus();

      // Show success with product name
      const product = loadedProducts.find(p => p.id === productId);
      connectedProductName.textContent = product?.name || product?.slug || 'your product';
      showSection(successSection);

    } catch (err) {
      hideStatus();
      showError(err.message || 'Connection failed. Please try again.');
      connectBtn.disabled = false;
    }
  });

  // Retry buttons
  retryBtn.addEventListener('click', () => {
    showSection(connectSection);
    connectBtn.disabled = !productSelect.value;
  });

  errorRetryBtn.addEventListener('click', () => {
    showSection(connectSection);
    connectBtn.disabled = !productSelect.value;
  });

  connectAnotherBtn.addEventListener('click', () => {
    resetForm();
  });
});
