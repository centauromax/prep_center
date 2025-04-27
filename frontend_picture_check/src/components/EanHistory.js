import React from 'react';

function EanHistory({ items }) {
  // Formatta la data nel formato italiano
  const formatDate = (dateString) => {
    const options = { year: 'numeric', month: '2-digit', day: '2-digit' };
    return new Date(dateString).toLocaleDateString('it-IT', options);
  };

  // Ordina gli elementi per data decrescente
  const sortedItems = [...items].sort((a, b) => new Date(b.data) - new Date(a.data));

  return (
    <div className="ean-history-container">
      {sortedItems.length === 0 ? (
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
            {sortedItems.map((item) => (
              <tr key={item.id}>
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

export default EanHistory; 