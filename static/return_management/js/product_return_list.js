$(document).ready(function() {
    var table = $('#productTable').DataTable({
        paging: true,
        pageLength: 500,
        lengthChange: false,
        searching: false,
        scrollY: 'calc(100vh - 265px)', // Regola in base all'altezza di header/footer
        scrollX: true,
        scrollCollapse: true,
        fixedHeader: true,
        language: {
            paginate: {
                next: '', // Remove the "Successivo" label
                previous: '' // Remove the "Precedente" label
            },
            info: 'Visualizzazione da _START_ a _END_ di _TOTAL_ elementi'
        },
        dom: "<'top'f>rt<'bottom'lp><'clear'>",
        drawCallback: function(settings) {
            var api = this.api();
            var info = api.page.info();
            $('#tableInfo').html(
                'Showing ' + (info.start + 1) + ' to ' + info.end + ' of ' + info.recordsTotal + ' entries'
            );

            // Move pagination to custom footer
            var pagination = $(api.table().container()).find('.dataTables_paginate');
            if (pagination.length) {
                $('#tablePagination').html(pagination.clone(true, true));
            }
        },
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
