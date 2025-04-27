import React, { useRef, useEffect } from 'react';

function EanInput({ ean, onEanChange, onSubmit, isLoading }) {
  const inputRef = useRef(null);
  
  // Focus sempre sull'input EAN
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, [ean, isLoading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(e);
    // Refocus dopo submit
    if (inputRef.current) {
      setTimeout(() => inputRef.current.focus(), 0);
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="ean-input-form">
      <div className="form-group">
        <input
          ref={inputRef}
          id="eanFnskuInput"
          type="text"
          className="form-control"
          value={ean}
          onChange={(e) => onEanChange(e.target.value)}
          placeholder="Inserisci il codice EAN/FNSKU"
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