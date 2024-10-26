$(document).ready(function() {
    // Funzione per formattare i numeri
    function formatNumber(num, isCurrency = false) {
        if (num < 1) {
            num = num.toFixed(20).match(/^-?\d*\.?0*[1-9]/)[0];
        } else {
            num = num.toFixed(1);
        }
        if (isCurrency) {
            return '€ ' + num;
        }
        return num;
    }

    // Inizializzazione DataTable
    const dataTable = $('#resultsTable').DataTable({
        scrollY: '50vh',
        scrollX: true,
        scrollCollapse: true,
        paging: false,
        searching: true,
        info: false,
        autoWidth: false,
        columns: [
            { data: 'Product' },
            { data: 'Marketplace' },
            { data: 'Product volume' },
            { data: 'Total volume' },
            { data: 'Amazon monthly cost' },
            { data: 'Our monthly rate' },
            { data: 'Our monthly cost' }
        ],
        columnDefs: [
            { width: '30%', targets: 0 },
            { width: '10%', targets: '_all' },
            { className: 'dt-center', targets: 1 }
        ],
        fixedHeader: true,
        responsive: true,
        initComplete: function(settings, json) {
            this.api().columns.adjust();
        }
    });

    // Ricalcola le dimensioni della tabella quando la finestra viene ridimensionata
    $(window).on('resize', function () {
        dataTable.columns.adjust();
    });

    // Gestione upload file
    $('#uploadForm').on('submit', function(e) {
        e.preventDefault();
        console.log('Form submitted'); // Debug log

        const fileInput = $('#fileInput')[0];
        if (fileInput.files.length === 0) {
            console.log('No file selected'); // Debug log
            showAlert('error', 'Seleziona un file da analizzare');
            return false;
        }
        
        console.log('File selected:', fileInput.files[0].name); // Debug log

        const formData = new FormData(this);

        $.ajax({
            url: '/fbasaving/upload/',  // Assicurati che questo URL sia corretto
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                console.log('Response received:', response);
                if (response.table_data) {
                    dataTable.clear().rows.add(response.table_data).draw();
                    
                    // Aggiorna gli altri risultati con controlli aggiuntivi
                    if (response.total_amazon_cost !== undefined) {
                        $('#totalAmazonCost').text(response.total_amazon_cost.toFixed(2));
                    } else {
                        console.error('total_amazon_cost is undefined');
                    }
                    if (response.total_prep_center_cost !== undefined) {
                        $('#totalPrepCenterCost').text(response.total_prep_center_cost.toFixed(2));
                    } else {
                        console.error('total_prep_center_cost is undefined');
                    }
                    if (response.saving !== undefined) {
                        $('#saving').text(response.saving.toFixed(2));
                    } else {
                        console.error('saving is undefined');
                    }
                    if (response.saving_percentage !== undefined) {
                        $('#savingPercentage').text(response.saving_percentage.toFixed(2));
                    } else {
                        console.error('saving_percentage is undefined');
                    }
                    
                    // Mostra le sezioni dei risultati e della tabella
                    $('.results-section').show();
                    $('.datatable-section').show();
                } else if (response.error) {
                    showAlert('error', response.error);
                } else {
                    console.error('Unexpected response structure:', response);
                    showAlert('error', 'Risposta del server non valida');
                }
            },
            error: function(xhr, status, error) {
                console.error('AJAX error:', xhr.status, error);
                showAlert('error', 'Si è verificato un errore durante l\'elaborazione del file.');
            }
        });
    });

    // Funzione per mostrare gli alert
    function showAlert(type, message) {
        alert(message); // Per ora, usiamo un semplice alert. Puoi migliorarlo in seguito.
    }

    // Funzione per ottenere l'URL del file lingua per DataTables
    function getLangUrl() {
        const currentLang = document.documentElement.lang;
        if (currentLang === 'it') {
            return "//cdn.datatables.net/plug-ins/1.13.7/i18n/it-IT.json";
        }
        return "//cdn.datatables.net/plug-ins/1.13.7/i18n/en-GB.json";
    }
});
