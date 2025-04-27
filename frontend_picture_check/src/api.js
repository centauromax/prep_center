// Ottieni l'URL base delle API dalla variabile d'ambiente o usa il valore predefinito
const API_BASE_URL = process.env.REACT_APP_API_URL || '/picture_check/api';

// Funzione di utilità per gestire le chiamate API
async function fetchAPI(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `Errore API: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`Errore nella chiamata API a ${endpoint}:`, error);
    throw error;
  }
}

// Ottiene la lista dei clienti attivi
export async function getClienti() {
  return await fetchAPI('/clienti/');
}

// Verifica se per un determinato EAN/FNSKU e Cliente sono già state fatte le foto
export async function checkEan(ean, cliente) {
  const clienteParam = encodeURIComponent(cliente);
  return await fetchAPI(`/check/${ean}/?cliente=${clienteParam}`);
}

// Salva un nuovo EAN per cui le foto non sono state fatte
export async function salvaEan(data) {
  return await fetchAPI('/salva/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// Ottiene la lista degli ultimi EAN verificati
export async function getListaEan() {
  return await fetchAPI('/lista/');
} 