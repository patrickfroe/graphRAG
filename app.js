const viewGraphButton = document.getElementById('view-graph-btn');
const graphModal = document.getElementById('graph-modal');
const graphFrame = document.getElementById('graph-frame');
const closeModalButton = document.getElementById('close-modal');

let latestEntityKeys = [];

function normalizeEntityKeys(response) {
  const keys = response?.entity_keys;
  if (!Array.isArray(keys)) return [];
  return keys.filter((key) => typeof key === 'string' && key.trim().length > 0);
}

function openGraphModal(entityKeys) {
  const params = new URLSearchParams();
  if (entityKeys.length > 0) {
    params.set('entity_keys', entityKeys.join(','));
  }

  graphFrame.src = `/graph/preview${params.toString() ? `?${params.toString()}` : ''}`;
  graphModal.classList.add('open');
  graphModal.setAttribute('aria-hidden', 'false');
}

function closeGraphModal() {
  graphModal.classList.remove('open');
  graphModal.setAttribute('aria-hidden', 'true');
  graphFrame.src = 'about:blank';
}

function handleChatResponse(response) {
  latestEntityKeys = normalizeEntityKeys(response);

  if (latestEntityKeys.length > 0) {
    viewGraphButton.style.display = 'inline-block';
    viewGraphButton.disabled = false;
  } else {
    viewGraphButton.style.display = 'none';
  }
}

viewGraphButton.addEventListener('click', () => openGraphModal(latestEntityKeys));
closeModalButton.addEventListener('click', closeGraphModal);
graphModal.addEventListener('click', (event) => {
  if (event.target === graphModal) {
    closeGraphModal();
  }
});

window.handleChatResponse = handleChatResponse;
const messageList = document.getElementById('messageList');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const messageTemplate = document.getElementById('messageTemplate');

function createMessage({ role, content, sources = [], loading = false }) {
  const node = messageTemplate.content.firstElementChild.cloneNode(true);
  const roleText = role === 'user' ? 'Du' : 'Assistent';

  node.classList.add(role);
  if (loading) {
    node.classList.add('loading');
  }

  node.querySelector('.message-role').textContent = roleText;
  node.querySelector('.message-content').textContent = content;

  const sourceList = node.querySelector('.message-sources');
  if (sources.length) {
    const label = document.createElement('li');
    label.textContent = 'Quellen:';
    label.style.listStyle = 'none';
    label.style.fontWeight = '700';
    label.style.marginLeft = '-20px';
    sourceList.appendChild(label);

    sources.forEach((source) => {
      const item = document.createElement('li');
      item.textContent = source;
      sourceList.appendChild(item);
    });
  }

  messageList.appendChild(node);
  messageList.scrollTop = messageList.scrollHeight;
  return node;
}

async function sendMessage(message) {
  const response = await fetch('/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  createMessage({ role: 'user', content: message });
  messageInput.value = '';

  sendButton.disabled = true;
  const loadingNode = createMessage({
    role: 'assistant',
    content: 'Antwort wird geladen…',
    loading: true,
  });

  try {
    const data = await sendMessage(message);
    const answer = data.answer ?? 'Keine Antwort erhalten.';
    const sources = Array.isArray(data.sources) ? data.sources : [];

    loadingNode.remove();
    createMessage({ role: 'assistant', content: answer, sources });
  } catch (error) {
    loadingNode.remove();
    createMessage({
      role: 'assistant',
      content: `Fehler beim Laden der Antwort: ${error.message}`,
    });
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
});
