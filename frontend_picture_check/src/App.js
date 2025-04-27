import React, { useState, useEffect } from 'react';
import ClienteSelect from './components/ClienteSelect';
import EanInput from './components/EanInput';
import EsitoMessage from './components/EsitoMessage';
import EanHistory from './components/EanHistory';
import { getClienti, checkEan, salvaEan, getListaEan } from './api';
import { playAffermazione, playNegazione } from './utils/suoni';
import settingsIcon from './assets/settings.svg';
import logoImg from './assets/logo.jpg';

function App() {
  const [clienti, setClienti] = useState([]);
  const [clienteSelezionato, setClienteSelezionato] = useState('');
  const [ean, setEan] = useState('');
  const [esitoMessage, setEsitoMessage] = useState({ ean: '', messaggio: '' });
  const [eanHistory, setEanHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

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
      return;
    }
    
    if (!clienteSelezionato) {
      return;
    }
    
    try {
      setIsLoading(true);
      
      // Verifica l'EAN/FNSKU + Cliente
      const risposta = await checkEan(ean, clienteSelezionato);
      let tipoEsito = 'success';
      let messaggio = risposta.messaggio;
      if (risposta.messaggio && risposta.messaggio.toLowerCase().includes('da realizzare')) {
        tipoEsito = 'warning';
        messaggio = 'Foto da inviare';
      }
      if (risposta.messaggio && risposta.messaggio.toLowerCase().includes('già realizzate')) {
        tipoEsito = 'success';
        messaggio = 'Foto già inviata';
      }
      if (risposta.messaggio && risposta.messaggio.toLowerCase().includes('non valido')) {
        tipoEsito = 'error';
      }
      setEsitoMessage({
        ean: risposta.ean,
        messaggio,
        tipoEsito
      });
      
      // Riproduci il suono appropriato
      if (risposta.foto_da_fare) {
        playAffermazione();
        
        // Salva l'EAN nel database
        await salvaEan({
          ean: risposta.ean,
          cliente: clienteSelezionato
        });
        
        // Aggiorna la cronologia immediatamente
        const nuovaCronologia = await getListaEan();
        setEanHistory(nuovaCronologia);
      } else {
        playNegazione();
      }
      
      // Resetta il campo EAN
      setEan('');
    } catch (err) {
      setEsitoMessage({
        ean: ean,
        messaggio: 'Codice EAN/FNSKU non valido: deve essere una stringa numerica di 12 o 13 cifre o alfanumerica di 10 caratteri.',
        tipoEsito: 'error'
      });
      setEan('');
      console.error('Errore nella verifica dell\'EAN:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    document.title = 'Verifica Foto Prodotti';
  }, []);

  return (
    <div className="app-container">
      <div className="topbar">
        <div className="topbar-left">
          <img src={logoImg} alt="Logo" className="topbar-logo" />
          <span className="topbar-title small-title">FbaPrepCenterItaly</span>
        </div>
        <div className="topbar-right">
          <img src={settingsIcon} alt="Impostazioni" className="settings-icon" />
        </div>
      </div>
      <div className="page-title-container">
        <h1 className="page-title">Verifica Foto Prodotti</h1>
      </div>
      <main className="app-content">
        <div className="card cliente-section">
          <h2>Seleziona Cliente</h2>
          <ClienteSelect 
            clienti={clienti} 
            clienteSelezionato={clienteSelezionato} 
            onClienteChange={handleClienteChange} 
          />
        </div>
        
        <div className="card ean-section">
          <h2>Verifica EAN/FNSKU</h2>
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
            <EsitoMessage ean={esitoMessage.ean} messaggio={esitoMessage.messaggio} tipoEsito={esitoMessage.tipoEsito} />
          </div>
        )}
        
        <div className="card history-section">
          <h2>Cronologia EAN/FNSKU</h2>
          <EanHistory items={eanHistory} />
        </div>
      </main>
      
      <footer className="app-footer">
        <p>&copy; {new Date().getFullYear()} Zacideas srl</p>
      </footer>
    </div>
  );
}

export default App; 