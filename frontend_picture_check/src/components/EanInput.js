import React, { useRef, useEffect } from 'react';

function EanInput({ ean, onEanChange, onSubmit, isLoading }) {
  const inputRef = useRef(null);
  
  // Focus sull'input all'avvio e quando l'EAN viene azzerato
  useEffect(() => {
    if (ean === '' && inputRef.current) {
      inputRef.current.focus();
    }
  }, [ean]);
  
  return (
    <form onSubmit={onSubmit} className="ean-input-form">
      <div className="form-group">
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

export default EanInput; 