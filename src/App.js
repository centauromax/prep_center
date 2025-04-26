import React, { useState, useEffect } from 'react';

function ClienteSelect({ clienti, clienteSelezionato, onClienteChange }) {
  return (
    <div className="cliente-select-container">
      <select 
        className="form-select"
        value={clienteSelezionato}
        onChange={(e) => onClienteChange(e.target.value)}
      >
        {clienti.length === 0 ? (
          <option value="">Caricamento clienti...</option>
        ) : (
          clienti.map((cliente, index) => (
            <option key={index} value={cliente.nome || cliente}>
              {cliente.nome || cliente}
            </option>
          ))
        )}
      </select>
    </div>
  );
}

function EanInput({ ean, onEanChange, onSubmit, isLoading }) {
  const inputRef = React.useRef(null);
  
  // Focus sull'input all'avvio e quando l'EAN viene azzerato
  useEffect(() => {
    if (ean === '' && inputRef.current) {
      inputRef.current.focus();
    }
  }, [ean]);
  
  return (
    <form onSubmit={onSubmit} className="ean-input-form">
      <div className="form-group">
        <label htmlFor="eanInput" className="form-label">Codice EAN:</label>
        <input
          ref={inputRef}
          id="eanInput"
          type="text"
          className="form-control"
          value={ean}
          onChange={(e) => onEanChange(e.target.value)}
          placeholder="Inserisci il codice EAN"
          disabled={isLoading}
          autoComplete="off"
        />
      </div>
      <button 
        type="submit" 
        className="btn btn-primary mt-2"
        disabled={isLoading || !ean}
      >
        {isLoading ? 'Verifica in corso...' : 'Verifica'}
      </button>
    </form>
  );
}

function EsitoMessage({ ean, messaggio }) {
  return (
    <div className="esito-message">
      <div className="esito-item">
        <strong>EAN:</strong> {ean}
      </div>
      <div className="esito-item">
        <strong>Esito:</strong> {messaggio}
      </div>
    </div>
  );
}

function EanHistory({ items }) {
  // Formatta la data nel formato italiano
  const formatDate = (dateString) => {
    if (!dateString) return '';
    const options = { year: 'numeric', month: '2-digit', day: '2-digit' };
    return new Date(dateString).toLocaleDateString('it-IT', options);
  };

  return (
    <div className="ean-history-container">
      {!items || items.length === 0 ? (
        <p className="text-center">Nessun EAN nella cronologia</p>
      ) : (
        <table className="table table-striped">
          <thead>
            <tr>
              <th>Data</th>
              <th>EAN</th>
              <th>Cliente</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr key={index}>
                <td>{formatDate(item.data)}</td>
                <td>{item.ean}</td>
                <td>{item.cliente}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// Mock API functions per test
const mockApiCalls = {
  getClienti: async () => {
    return [
      { id: 1, nome: 'Cliente A' },
      { id: 2, nome: 'Cliente B' },
      { id: 3, nome: 'Cliente C' }
    ];
  },
  checkEan: async (ean) => {
    // Simula esito random
    const random = Math.random();
    const fotoDaFare = random > 0.5;
    return {
      ean: ean,
      messaggio: fotoDaFare ? 'Le foto devono essere fatte.' : 'Le foto sono già state fatte.',
      foto_da_fare: fotoDaFare
    };
  },
  salvaEan: async (data) => {
    console.log('Salvato EAN:', data);
    return { success: true };
  },
  getListaEan: async () => {
    return [
      { id: 1, data: new Date().toISOString(), ean: '8001234567890', cliente: 'Cliente A' },
      { id: 2, data: new Date(Date.now() - 86400000).toISOString(), ean: '8004567890123', cliente: 'Cliente B' }
    ];
  }
};

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
      // Usa l'API mock in sviluppo
      const data = await mockApiCalls.getClienti();
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
      // Usa l'API mock in sviluppo
      const data = await mockApiCalls.getListaEan();
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
      const risposta = await mockApiCalls.checkEan(ean);
      setEsitoMessage({
        ean: risposta.ean,
        messaggio: risposta.messaggio
      });
      
      // Se le foto devono essere fatte, salva l'EAN
      if (risposta.foto_da_fare) {
        // Salva l'EAN nel database
        await mockApiCalls.salvaEan({
          ean: risposta.ean,
          cliente: clienteSelezionato
        });
        
        // Aggiorna la cronologia
        loadEanHistory();
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