/* Script per spostare i file compilati React */
const fs = require('fs-extra');
const path = require('path');

// Definizione dei percorsi
const buildDir = path.join(__dirname, 'build');

// Directory di output per i file statici serviti dal CDN
const outputDir = path.join(__dirname, '../dist/picture_check');

console.log('Percorsi:');
console.log(`- Build dir: ${buildDir}`);
console.log(`- Output dir: ${outputDir}`);

// Assicurati che le directory di destinazione esistano
console.log('Creazione directory di destinazione...');
fs.ensureDirSync(outputDir);

// Verifica se la build esiste
if (!fs.existsSync(buildDir)) {
  console.error(`Errore: directory build non trovata in ${buildDir}`);
  process.exit(1);
}

// Copia tutti i file della build nella directory di output
console.log('Copia dei file...');
try {
  fs.copySync(buildDir, outputDir, { overwrite: true });
  console.log('File copiati con successo');
} catch (err) {
  console.error(`Errore nella copia dei file: ${err}`);
  process.exit(1);
}

console.log(`Build completata e file copiati in ${outputDir}`); 