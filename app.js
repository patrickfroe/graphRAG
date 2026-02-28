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
