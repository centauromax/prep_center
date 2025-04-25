// Percorsi dei file audio
const SUONO_AFFERMAZIONE = '/static/picture_check/sounds/affermazione.mp3';
const SUONO_NEGAZIONE = '/static/picture_check/sounds/negazione.mp3';

// Cache degli elementi audio
let audioAffermazione = null;
let audioNegazione = null;

// Funzione per riprodurre il suono di affermazione
export function playAffermazione() {
  if (!audioAffermazione) {
    audioAffermazione = new Audio(SUONO_AFFERMAZIONE);
  }
  
  audioAffermazione.currentTime = 0;
  audioAffermazione.play().catch(err => {
    console.error('Errore nella riproduzione del suono di affermazione:', err);
  });
}

// Funzione per riprodurre il suono di negazione
export function playNegazione() {
  if (!audioNegazione) {
    audioNegazione = new Audio(SUONO_NEGAZIONE);
  }
  
  audioNegazione.currentTime = 0;
  audioNegazione.play().catch(err => {
    console.error('Errore nella riproduzione del suono di negazione:', err);
  });
}

// Funzione per precaricare i suoni
export function preloadSounds() {
  audioAffermazione = new Audio(SUONO_AFFERMAZIONE);
  audioNegazione = new Audio(SUONO_NEGAZIONE);
} 