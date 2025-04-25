/* Script per spostare i file compilati React nella directory servita da Django */
const fs = require('fs-extra');
const path = require('path');

// Definizione dei percorsi
const buildDir = path.join(__dirname, 'build');
const staticDir = path.join(__dirname, '../../backend/static/picture_check/react');
const templatesDir = path.join(__dirname, '../../backend/picture_check/templates/picture_check/react');

console.log('Percorsi:');
console.log(`- Build dir: ${buildDir}`);
console.log(`- Static dir: ${staticDir}`);
console.log(`- Templates dir: ${templatesDir}`);

// Assicurati che le directory di destinazione esistano
console.log('Creazione directory di destinazione...');
fs.ensureDirSync(staticDir);
fs.ensureDirSync(templatesDir);

// Verifica se la build esiste
if (!fs.existsSync(buildDir)) {
  console.error(`Errore: directory build non trovata in ${buildDir}`);
  process.exit(1);
}

// Verifica se ci sono i file static nella build
const staticSourceDir = path.join(buildDir, 'static');
if (!fs.existsSync(staticSourceDir)) {
  console.error(`Errore: directory static non trovata in ${staticSourceDir}`);
  process.exit(1);
}

// Copia i file statici (JS, CSS, immagini) nella directory static di Django
console.log('Copia dei file statici...');
try {
  fs.copySync(
    staticSourceDir,
    path.join(staticDir, 'static'),
    { overwrite: true }
  );
  console.log('File statici copiati con successo');
} catch (err) {
  console.error(`Errore nella copia dei file statici: ${err}`);
  process.exit(1);
}

// Verifica se esiste il file index.html
const indexHtmlPath = path.join(buildDir, 'index.html');
if (!fs.existsSync(indexHtmlPath)) {
  console.error(`Errore: file index.html non trovato in ${indexHtmlPath}`);
  process.exit(1);
}

// Aggiorna i percorsi nel file index.html
console.log('Aggiornamento dei percorsi in index.html...');
try {
  let indexHtml = fs.readFileSync(indexHtmlPath, 'utf8');
  indexHtml = indexHtml.replace(
    /\/static\//g,
    '/static/picture_check/react/static/'
  );

  // Salva l'index.html come template Django
  const targetIndexPath = path.join(templatesDir, 'index.html');
  fs.writeFileSync(targetIndexPath, indexHtml);
  console.log(`index.html aggiornato e salvato in ${targetIndexPath}`);
} catch (err) {
  console.error(`Errore nell'aggiornamento di index.html: ${err}`);
  process.exit(1);
}

console.log('File della build copiati nelle directory di Django con successo!');
console.log(`
Riepilogo:
- File statici (JS/CSS): ${path.join(staticDir, 'static')}
- Template HTML: ${path.join(templatesDir, 'index.html')}
`);

// Verifica finale che i file siano stati copiati correttamente
if (!fs.existsSync(path.join(templatesDir, 'index.html'))) {
  console.error('ATTENZIONE: index.html non è stato copiato correttamente!');
} else {
  console.log('Verifica finale: index.html copiato correttamente.');
} 