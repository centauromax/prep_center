// VERSIONE 1.1 - Log di verifica aggiornato
console.log('=== Loading main.js version 1.1 ===');

let dataTable = null;

// Log all'avvio
$(document).ready(function () {
    console.log('=== Document Ready ===');
    // Verifica se ci sono altri script DataTables
    console.log('DataTables scripts loaded:',
        $('script').filter(function () {
            return $(this).attr('src') && $(this).attr('src').includes('dataTables');
        }).map(function () {
            return $(this).attr('src');
        }).get()
    );
    // Verifica se la tabella esiste già
    console.log('Table initialization status:', {
        tableExists: $('#resultsTable').length > 0,
        isDataTable: $.fn.DataTable.isDataTable('#resultsTable'),
        tableHtml: $('#resultsTable').html()
    });
});

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
        processData: false,
        contentType: false,
        success: function (response) {
            console.log('=== AJAX Success ===');
            console.log('Response data:', response);

            if (response.table_data) {
                console.log('=== Table Initialization Start ===');
                console.log('Current dataTable instance:', dataTable ? 'exists' : 'null');
                console.log('Container width before init:', $('.datatable-section').width());

                // Distruggi la tabella esistente se presente
                if (dataTable) {
                    console.log('Destroying existing DataTable');
                    dataTable.destroy();
                    $('#resultsTable').empty();
                }

                // Forza la larghezza del wrapper
                $('.dataTables_wrapper').css('width', '100%');

                console.log('Creating new DataTable instance');

                // Aggiorna la configurazione di DataTables
                dataTable = $('#resultsTable').DataTable({
                    scrollY: '50vh',
                    scrollX: true,
                    scrollCollapse: true,
                    paging: false,
                    searching: false,
                    info: false,
                    autoWidth: false,
                    data: response.table_data,
                    order: [[5, 'desc']], // Ordina per la colonna 'Amazon monthly rate'
                    columns: [
                        { data: 'Product', className: 'text-start' },
                        { data: 'Market', className: 'text-center' },
                        { data: 'Product volume', className: 'text-start' },
                        { data: 'Total volume', className: 'text-start' },
                        { data: 'Amazon monthly cost', className: 'text-start' },
                        { data: 'Amazon monthly rate', className: 'text-start' },
                        { data: 'Our monthly rate', className: 'text-start' },
                        { data: 'Our monthly cost', className: 'text-start' }
                    ],
                    headerCallback: function(thead, data, start, end, display) {
                        $(thead).show();  // Assicura che l'header sia visibile
                    },
                    columnDefs: [
                        {
                            // Colonne che richiedono formattazione numerica semplice
                            targets: [2, 3], // Indici delle colonne 'Product volume' e 'Total volume'
                            render: function (data, type, row, meta) {
                                if (type === 'display' || type === 'filter') {
                                    return formatNumber(data);
                                }
                                return data;
                            }
                        },
                        {
                            // Colonne che richiedono formattazione come valuta
                            targets: [4, 5, 6, 7], // Indici delle colonne di costi e tariffe
                            render: function (data, type, row, meta) {
                                if (type === 'display' || type === 'filter') {
                                    return formatNumber(data, true);
                                }
                                return data;
                            }
                        },
                        // Impostazione delle larghezze delle colonne
                        { width: '30%', targets: 0 },
                        { width: '8%', targets: 1 },
                        { width: '10%', targets: 2 },
                        { width: '10%', targets: 3 },
                        { width: '10%', targets: 4 },
                        { width: '12%', targets: 5 },
                        { width: '10%', targets: 6 },
                        { width: '10%', targets: 7 }
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
                    }
                });

                // Aggiorna gli altri risultati con controlli aggiuntivi
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

                // Mostra le sezioni dei risultati e della tabella
                $('.results-section').show();
                $('.datatable-section').show();

                console.log('=== Final Table State ===');
                console.log('Container visible:', $('.datatable-section').is(':visible'));
                console.log('Container width:', $('.datatable-section').width());
                console.log('Table width:', $('#resultsTable').width());
                console.log('Scroll wrapper width:', $('.dataTables_scrollBody').width());
            } else if (response.error) {
                showAlert('error', response.error);
            } else {
                console.error('Unexpected response format:', response);
            }
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
