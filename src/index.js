import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// Funzione per verificare se siamo nell'URL corretto prima di montare l'app
function shouldRenderApp() {
  const path = window.location.pathname;
  const currentHost = window.location.hostname;
  
  // L'app React gestisce solo i percorsi picture_check
  if (path.startsWith('/picture_check/') || 
      path.startsWith('/en/picture_check/') || 
      path.startsWith('/it/picture_check/')) {
    return true;
  }
  
  // Percorsi specifici da reindirizzare al backend Django direttamente
  if (path.startsWith('/fbasaving/') || 
      path.startsWith('/en/fbasaving/') || 
      path.startsWith('/it/fbasaving/')) {
    // Reindirizza direttamente al backend Django senza parametri aggiuntivi
    const djangoBackendUrl = 'https://prepcenter-production.up.railway.app';
    window.location.replace(djangoBackendUrl + path);
    return false;
  }
  
  // Per evitare loop di reindirizzamento, controlliamo se abbiamo un parametro URL che indica
  // che siamo già stati reindirizzati
  const params = new URLSearchParams(window.location.search);
  if (params.has('from_redirect')) {
    // Siamo già stati reindirizzati, non reindirizzare di nuovo
    console.error('Errore: percorso non supportato:', path);
    // Mostra un messaggio all'utente
    document.body.innerHTML = '<div style="text-align: center; margin-top: 50px;"><h1>Errore</h1><p>Questo percorso non è supportato da questa applicazione.</p><p><a href="/picture_check/">Vai a Picture Check</a></p><p><a href="/fbasaving/">Vai a FBA Saving</a></p></div>';
    return false;
  }
  
  // Per tutti gli altri percorsi, reindirizza al backend Django con parametro per evitare loop
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