/* Script per spostare i file compilati React nella directory servita da Django */
const fs = require('fs-extra');
const path = require('path');

const buildDir = path.join(__dirname, 'build');
const staticDir = path.join(__dirname, '../../backend/static/picture_check/react');
const templatesDir = path.join(__dirname, '../../backend/picture_check/templates/picture_check/react');

// Assicurati che le directory di destinazione esistano
fs.ensureDirSync(staticDir);
fs.ensureDirSync(templatesDir);

// Copia i file statici (JS, CSS, immagini) nella directory static di Django
fs.copySync(
  path.join(buildDir, 'static'),
  path.join(staticDir, 'static'),
  { overwrite: true }
);

// Aggiorna i percorsi nel file index.html
let indexHtml = fs.readFileSync(path.join(buildDir, 'index.html'), 'utf8');
indexHtml = indexHtml.replace(
  /\/static\//g,
  '/static/picture_check/react/static/'
);

// Salva l'index.html come template Django
fs.writeFileSync(
  path.join(templatesDir, 'index.html'),
  indexHtml
);

console.log('File della build copiati nelle directory di Django con successo!'); 