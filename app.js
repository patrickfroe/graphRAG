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
