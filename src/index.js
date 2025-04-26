import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// Funzione per verificare se siamo nell'URL corretto prima di montare l'app
function shouldRenderApp() {
  const path = window.location.pathname;
  
  // L'app React gestisce solo i percorsi picture_check
  if (path.startsWith('/picture_check/') || 
      path.startsWith('/en/picture_check/') || 
      path.startsWith('/it/picture_check/')) {
    return true;
  }
  
  // Per fbasaving, creiamo un iframe che punta direttamente al backend Django
  if (path.startsWith('/fbasaving/') || 
      path.startsWith('/en/fbasaving/') || 
      path.startsWith('/it/fbasaving/')) {
    console.log('Richiesta per fbasaving rilevata, creo un iframe al backend');
    
    // Pulisce qualsiasi contenuto esistente
    document.body.innerHTML = '';
    document.body.style.margin = '0';
    document.body.style.padding = '0';
    document.body.style.overflow = 'hidden';
    
    // Crea un iframe a schermo intero che punta al backend Django
    const iframe = document.createElement('iframe');
    iframe.style.width = '100%';
    iframe.style.height = '100vh';
    iframe.style.border = 'none';
    iframe.style.overflow = 'hidden';
    
    // Su Railway, il backend Django potrebbe essere accessibile tramite un URL relativo,
    // poiché nginx.conf è configurato per fare proxy verso http://web:8000
    // Utilizziamo un URL relativo per massima compatibilità
    iframe.src = `/fbasaving-api${path}`;
    
    document.body.appendChild(iframe);
    return false;
  }
  
  // Per tutti gli altri percorsi sconosciuti
  document.body.innerHTML = `
    <div style="text-align: center; font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
      <h1 style="color: #2c3e50;">Percorso non supportato</h1>
      <p style="font-size: 18px; margin-bottom: 30px;">L'URL richiesto non è disponibile in questa applicazione.</p>
      <div style="margin-top: 30px;">
        <a href="/picture_check/" style="display: inline-block; padding: 10px 20px; background-color: #3498db; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px;">Vai a Picture Check</a>
        <a href="/fbasaving/" style="display: inline-block; padding: 10px 20px; background-color: #27ae60; color: white; text-decoration: none; border-radius: 4px;">Vai a FBA Saving</a>
      </div>
    </div>
  `;
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