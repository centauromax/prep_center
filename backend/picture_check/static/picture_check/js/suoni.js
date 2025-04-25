/**
 * Utility per la gestione dei suoni nell'app Picture Check
 */

// Suono di affermazione (quando le foto devono essere fatte)
const suonoAffermazione = new Audio('/static/picture_check/sounds/affermazione.mp3');

// Suono di negazione (quando le foto sono già state fatte)
const suonoNegazione = new Audio('/static/picture_check/sounds/negazione.mp3');

// Funzione per riprodurre il suono di affermazione
function playAffermazione() {
    suonoAffermazione.play();
}

// Funzione per riprodurre il suono di negazione
function playNegazione() {
    suonoNegazione.play();
}

// Esporta le funzioni
export { playAffermazione, playNegazione }; 