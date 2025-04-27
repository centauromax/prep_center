import React from 'react';

function EsitoMessage({ ean, messaggio, tipoEsito }) {
  let bgColor = '#2ecc40'; // verde di default
  if (tipoEsito === 'warning') bgColor = '#e57373'; // rosa/rosso
  if (tipoEsito === 'error') bgColor = '#d32f2f'; // rosso

  return (
    <div className="esito-message" style={{ backgroundColor: bgColor, color: '#fff' }}>
      <div className="esito-item">
        <strong>EAN:</strong> {ean}
      </div>
      <div className="esito-item">
        <strong>Esito:</strong> {messaggio}
      </div>
    </div>
  );
}

export default EsitoMessage; 