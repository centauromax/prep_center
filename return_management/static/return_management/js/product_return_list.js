$(document).ready(function() {
    var table = $('#productTable').DataTable({
        paging: true,
        pageLength: 500,
        lengthChange: false,
        searching: true,
        scrollY: 'calc(100vh - 300px)', // Regola in base all'altezza di header/footer
        scrollX: true,
        scrollCollapse: true,
        fixedHeader: true,
        language: {
            paginate: {
                next: 'Successivo',
                previous: 'Precedente'
            },
            info: 'Visualizzazione da _START_ a _END_ di _TOTAL_ elementi'
        },
        // Utilizza l'opzione 'dom' per posizionare gli elementi
        dom: "<'top'f>rt<'bottom'lpi>",
        initComplete: function() {
            var api = this.api();
            // Applica la ricerca per colonna
            api.columns().every(function() {
                var column = this;
                $('input', column.header()).on('keyup change clear', function() {
                    if (column.search() !== this.value) {
                        column.search(this.value).draw();
                    }
                });
            });
        }
    });

    // Ricerca globale
    $('#globalSearch').on('keyup', function() {
        table.search(this.value).draw();
    });
});
