import React from 'react';

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

export default EsitoMessage; 