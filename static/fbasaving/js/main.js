// VERSIONE 2.0 - Implementazione del server-side processing
console.log('=== Loading main.js version 2.0 ===');

let dataTable = null;

// Funzione di utilità per formattare i numeri
function formatNumber(value, isCurrency = false) {
    let num = parseFloat(value);
    if (isNaN(num)) return value; // Restituisce il valore originale se non è un numero

    if (isCurrency) {
        if (Math.abs(num) >= 1) {
            // Numeri >= 1: due cifre decimali
            return num.toLocaleString('it-IT', {
                style: 'currency',
                currency: 'EUR',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        } else {
            // Numeri < 1: una cifra significativa, tutte le cifre fino alla prima maggiore di zero
            return num.toLocaleString('it-IT', {
                style: 'currency',
                currency: 'EUR',
                maximumSignificantDigits: 1
            });
        }
    } else {
        if (Math.abs(num) < 1) {
            // Numeri < 1: una cifra significativa
            return num.toLocaleString('it-IT', {
                maximumSignificantDigits: 1
            });
        } else {
            // Numeri >= 1: una cifra decimale
            return num.toLocaleString('it-IT', {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1
            });
        }
    }
}

// Gestione upload file
$('#uploadForm').on('submit', function (e) {
    e.preventDefault();
    console.log('=== Form Submitted ===');
    console.log('Form data:', new FormData(this));

    const fileInput = $('#fileInput')[0];
    if (fileInput.files.length === 0) {
        console.log('No file selected');
        showAlert('error', 'Seleziona un file da analizzare');
        return false;
    }

    console.log('Selected file:', {
        name: fileInput.files[0].name,
        size: fileInput.files[0].size,
        type: fileInput.files[0].type
    });

    const formData = new FormData(this);

    $.ajax({
        url: '/fbasaving/upload/',
        type: 'POST',
        data: formData,
        dataType: 'json',  // Specifica il tipo di dati attesi
        processData: false,
        contentType: false,
        success: function (response) {
            console.log('=== AJAX Success ===');
            console.log('Response data:', response);

            if (response.total_amazon_cost !== undefined) {
                console.log('Formatting total_amazon_cost:', response.total_amazon_cost);
                $('#totalAmazonCost').text(formatNumber(response.total_amazon_cost, true));
            } else {
                console.error('total_amazon_cost is undefined');
            }
            if (response.total_prep_center_cost !== undefined) {
                console.log('Formatting total_prep_center_cost:', response.total_prep_center_cost);
                $('#totalPrepCenterCost').text(formatNumber(response.total_prep_center_cost, true));
            } else {
                console.error('total_prep_center_cost is undefined');
            }
            if (response.saving !== undefined) {
                console.log('Formatting saving:', response.saving);
                $('#saving').text(formatNumber(response.saving, true));
            } else {
                console.error('saving is undefined');
            }
            if (response.saving_percentage !== undefined) {
                console.log('Formatting saving_percentage:', response.saving_percentage);
                $('#savingPercentage').text(formatNumber(response.saving_percentage));
            } else {
                console.error('saving_percentage is undefined');
            }

            // Inizializza la DataTable con il server-side processing
            initializeDataTable();

            // Mostra le sezioni dei risultati e della tabella
            $('.results-section').show();
            $('.datatable-section').show();

            // Scroll semplice di 200px verso l'alto
            window.scrollTo({
                top: window.scrollY + 700,
                behavior: 'smooth'
            });

        },
        error: function (xhr, status, error) {
            console.error('=== AJAX Error ===', {
                status: xhr.status,
                error: error,
                response: xhr.responseText
            });
            showAlert('error', 'Si è verificato un errore durante l\'elaborazione del file.');
        }
    });
});

// Funzione per inizializzare la DataTable con server-side processing
function initializeDataTable() {
    // Distruggi la tabella esistente se presente
    if ($.fn.DataTable.isDataTable('#resultsTable')) {
        $('#resultsTable').DataTable().destroy();
        $('#resultsTable').empty();
    }

    // Ricrea l'header della tabella
    let headerHtml = `
        <thead>
            <tr>
                <th class="text-start">${translations.product}</th>
                <th class="text-end">${translations.productVolume}</th>
                <th class="text-end">${translations.totalVolume}</th>
                <th class="text-end">${translations.amazonMonthlyCost}</th>
                <th class="text-end">${translations.amazonMonthlyRate}</th>
                <th class="text-end">${translations.ourMonthlyRate}</th>
                <th class="text-end">${translations.ourMonthlyCost}</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;
    $('#resultsTable').html(headerHtml);

    // Inizializza la nuova DataTable
    $('#resultsTable').DataTable({
        serverSide: true,
        processing: true,
        ajax: {
            url: dataTablesUrl,  // Usa la variabile definita nel template
            type: 'POST',
            dataType: 'json',
            data: function (d) {
                // Aggiungi il token CSRF se necessario
                d.csrfmiddlewaretoken = getCSRFToken();
            },
            error: function (xhr, error, thrown) {
                console.error('=== DataTable AJAX Error ===', {
                    status: xhr.status,
                    error: error,
                    response: xhr.responseText
                });
                showAlert('error', 'Si è verificato un errore durante il caricamento dei dati della tabella.');
            }
        },
        pageLength: 300,  // Fissa il numero di righe per pagina a 300
        lengthChange: false,  // Nasconde il selettore del numero di righe per pagina
        scrollY: '50vh',
        scrollX: true,
        scrollCollapse: true,
        paging: true,
        searching: false,
        info: true,
        autoWidth: false,
        order: [[3, 'desc']], // Ordina per la colonna 'Costo mensile Amazon' in modo decrescente
        columns: [
            { data: 'Product', className: 'text-start' },
            { data: 'Product volume', className: 'text-end' },
            { data: 'Total volume', className: 'text-end' },
            { data: 'Amazon monthly cost', className: 'text-end' },
            { data: 'Amazon monthly rate', className: 'text-end' },
            { data: 'Our monthly rate', className: 'text-end' },
            { data: 'Our monthly cost', className: 'text-end' }
        ],
        headerCallback: function(thead, data, start, end, display) {
            $(thead).show();  // Forza la visualizzazione dell'header
        },
        columnDefs: [
            {
                // Colonne che richiedono formattazione numerica semplice
                targets: [1, 2], // Indici delle colonne 'Product volume' e 'Total volume'
                render: function (data, type, row, meta) {
                    if (type === 'display' || type === 'filter') {
                        return formatNumber(data);
                    }
                    return data;
                }
            },
            {
                // Colonne che richiedono formattazione come valuta
                targets: [3, 4, 5, 6], // Indici delle colonne di costi e tariffe
                render: function (data, type, row, meta) {
                    if (type === 'display' || type === 'filter') {
                        return formatNumber(data, true);
                    }
                    return data;
                }
            },
            // Impostazione delle larghezze delle colonne
            { width: '35%', targets: 0 },
            { width: '11%', targets: 1 },
            { width: '11%', targets: 2 },
            { width: '11%', targets: 3 },
            { width: '11%', targets: 4 },
            { width: '11%', targets: 5 },
            { width: '10%', targets: 6 }
        ],
        initComplete: function (settings, json) {
            console.log('=== DataTable InitComplete ===');

            // Forza la larghezza del wrapper e dei contenitori
            $('.dataTables_wrapper').css('width', '100%');
            $('.dataTables_scrollHead, .dataTables_scrollBody').css('width', '100%');

            // Sincronizza le larghezze
            const $scrollBody = $(this.api().table().container()).find('.dataTables_scrollBody');
            const $scrollHead = $(this.api().table().container()).find('.dataTables_scrollHead');
            const tableWidth = $scrollBody.find('table').width();

            $scrollHead.find('table').width(tableWidth);

            // Applica il wrapping all'header
            $(this.api().table().header()).find('th').css({
                'white-space': 'normal',
                'word-wrap': 'break-word'
            });

            // Forza il ricalcolo delle colonne
            this.api().columns.adjust();

            console.log('Widths after synchronization:', {
                wrapper: $('.dataTables_wrapper').width(),
                scrollHead: $scrollHead.width(),
                scrollBody: $scrollBody.width(),
                headerTable: $scrollHead.find('table').width(),
                bodyTable: $scrollBody.find('table').width()
            });
        },
        language: {
            url: getLangUrl()
        }
    });
}

// Funzione per mostrare gli alert
function showAlert(type, message) {
    alert(message);
}

// Funzione per ottenere l'URL del file lingua per DataTables
function getLangUrl() {
    const currentLang = document.documentElement.lang;
    if (currentLang === 'it') {
        return "//cdn.datatables.net/plug-ins/1.13.7/i18n/it-IT.json";
    }
    return "//cdn.datatables.net/plug-ins/1.13.7/i18n/en-GB.json";
}

// Funzione per ottenere il token CSRF
function getCSRFToken() {
    let csrfToken = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Verifica se il cookie inizia con 'csrftoken='
            if (cookie.substring(0, 10) === 'csrftoken=') {
                csrfToken = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }
    return csrfToken;
}

// Funzione per ottenere le traduzioni
function gettext(text) {
    if (typeof django !== 'undefined' && django.gettext) {
        return django.gettext(text);
    }
    return text;
}
