import React from 'react';

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
          clienti.map((cliente) => (
            <option key={cliente.id} value={cliente.nome}>
              {cliente.nome}
            </option>
          ))
        )}
      </select>
    </div>
  );
}

export default ClienteSelect; 