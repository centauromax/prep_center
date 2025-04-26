import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// Funzione per verificare se siamo nell'URL corretto prima di montare l'app
function shouldRenderApp() {
  const path = window.location.pathname;
  const currentHost = window.location.hostname;
  
  // Solo per picture_check - l'app React gestisce solo questi percorsi
  if (path.startsWith('/picture_check/') || 
      path.startsWith('/en/picture_check/') || 
      path.startsWith('/it/picture_check/')) {
    return true;
  }
  
  // Per evitare loop di reindirizzamento, controlliamo se abbiamo un parametro URL che indica
  // che siamo già stati reindirizzati
  const params = new URLSearchParams(window.location.search);
  if (params.has('from_redirect')) {
    // Siamo già stati reindirizzati, non reindirizzare di nuovo
    console.error('Errore: percorso non supportato:', path);
    // Mostra un messaggio all'utente
    document.body.innerHTML = '<div style="text-align: center; margin-top: 50px;"><h1>Errore</h1><p>Questo percorso non è supportato da questa applicazione.</p><p><a href="/picture_check/">Vai a Picture Check</a></p></div>';
    return false;
  }
  
  // Reindirizza al backend Django con parametro per evitare loop
  const djangoBackendUrl = 'https://prepcenter-production.up.railway.app';
  const targetUrl = djangoBackendUrl + path + (path.includes('?') ? '&' : '?') + 'from_redirect=1';
  
  // Usa replace invece di href per evitare di aggiungere alla cronologia
  window.location.replace(targetUrl);
  
  return false;
}

// Verifica se dobbiamo montare l'app
if (shouldRenderApp()) {
  const root = ReactDOM.createRoot(document.getElementById('root'));
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}