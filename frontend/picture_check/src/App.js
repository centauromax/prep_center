import React, { useState, useEffect } from 'react';
import ClienteSelect from './components/ClienteSelect';
import EanInput from './components/EanInput';
import EsitoMessage from './components/EsitoMessage';
import EanHistory from './components/EanHistory';
import { getClienti, checkEan, salvaEan, getListaEan } from './api';
import { playAffermazione, playNegazione } from './utils/suoni';

function App() {
  const [clienti, setClienti] = useState([]);
  const [clienteSelezionato, setClienteSelezionato] = useState('');
  const [ean, setEan] = useState('');
  const [esitoMessage, setEsitoMessage] = useState({ ean: '', messaggio: '' });
  const [eanHistory, setEanHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Carica i clienti all'avvio
  useEffect(() => {
    loadClienti();
    loadEanHistory();
  }, []);

  // Carica la lista dei clienti
  const loadClienti = async () => {
    try {
      setIsLoading(true);
      const data = await getClienti();
      setClienti(data);
      if (data.length > 0) {
        setClienteSelezionato(data[0].nome);
      }
    } catch (err) {
      setError('Errore nel caricamento dei clienti');
      console.error('Errore nel caricamento dei clienti:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Carica la cronologia degli EAN
  const loadEanHistory = async () => {
    try {
      setIsLoading(true);
      const data = await getListaEan();
      setEanHistory(data);
    } catch (err) {
      setError('Errore nel caricamento della cronologia EAN');
      console.error('Errore nel caricamento della cronologia EAN:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Gestisce il cambio del cliente selezionato
  const handleClienteChange = (cliente) => {
    setClienteSelezionato(cliente);
  };

  // Gestisce il cambio dell'EAN inserito
  const handleEanChange = (nuovoEan) => {
    setEan(nuovoEan);
  };

  // Gestisce il submit del modulo EAN
  const handleEanSubmit = async (e) => {
    e.preventDefault();
    
    if (!ean) {
      setError('Inserisci un codice EAN');
      return;
    }
    
    if (!clienteSelezionato) {
      setError('Seleziona un cliente');
      return;
    }
    
    try {
      setIsLoading(true);
      setError('');
      
      // Verifica l'EAN
      const risposta = await checkEan(ean);
      setEsitoMessage({
        ean: risposta.ean,
        messaggio: risposta.messaggio
      });
      
      // Riproduci il suono appropriato
      if (risposta.foto_da_fare) {
        playAffermazione();
        
        // Salva l'EAN nel database
        await salvaEan({
          ean: risposta.ean,
          cliente: clienteSelezionato
        });
        
        // Aggiorna la cronologia
        loadEanHistory();
      } else {
        playNegazione();
      }
      
      // Resetta il campo EAN
      setEan('');
    } catch (err) {
      setError('Errore nella verifica dell\'EAN');
      console.error('Errore nella verifica dell\'EAN:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Picture Check</h1>
      </header>
      
      <main className="app-content">
        {error && <div className="error-message">{error}</div>}
        
        <div className="card cliente-section">
          <h2>Seleziona Cliente</h2>
          <ClienteSelect 
            clienti={clienti} 
            clienteSelezionato={clienteSelezionato} 
            onClienteChange={handleClienteChange} 
          />
        </div>
        
        <div className="card ean-section">
          <h2>Verifica EAN</h2>
          <EanInput 
            ean={ean} 
            onEanChange={handleEanChange} 
            onSubmit={handleEanSubmit} 
            isLoading={isLoading} 
          />
        </div>
        
        {esitoMessage.ean && (
          <div className="card esito-section">
            <h2>Esito Verifica</h2>
            <EsitoMessage ean={esitoMessage.ean} messaggio={esitoMessage.messaggio} />
          </div>
        )}
        
        <div className="card history-section">
          <h2>Cronologia EAN</h2>
          <EanHistory items={eanHistory} />
        </div>
      </main>
      
      <footer className="app-footer">
        <p>&copy; {new Date().getFullYear()} Prep Center</p>
      </footer>
    </div>
  );
}

export default App; 