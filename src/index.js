import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// Funzione per verificare se siamo nell'URL corretto prima di montare l'app
function shouldRenderApp() {
  const path = window.location.pathname;
  if (!path.startsWith('/picture_check/') && 
      !path.startsWith('/en/picture_check/') && 
      !path.startsWith('/it/picture_check/')) {
    // Redirect al backend Django per tutti gli altri URL
    window.location.href = 'https://prepcenter-production.up.railway.app' + path;
    return false;
  }
  return true;
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