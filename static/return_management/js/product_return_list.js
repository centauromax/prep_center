$(document).ready(function() {
    var table = $('#productTable').DataTable({
        paging: true,
        pageLength: 500,
        lengthChange: false,
        searching: true,
        scrollY: 'calc(100vh - 280px)', // Adjust for new layout with header/footer
        scrollX: true,
        scrollCollapse: true,
        fixedHeader: true,
        language: {
            paginate: {
                next: '<i class="fas fa-chevron-right"></i>', // Use icons for navigation
                previous: '<i class="fas fa-chevron-left"></i>'
            },
            info: 'Showing _START_ to _END_ of _TOTAL_ entries'
        },
        dom: "<'top-bar-controls'f>rt<'bottom-footer-info'lp><'clear'>",
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
            // Apply search for each column
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

    // Global search with better UI
    $('#globalSearch').on('keyup', function() {
        table.search(this.value).draw();
    });

    // Update styles for better alignment and visuals
    $('.middle-container__button').addClass('btn btn-primary');
    $('#globalSearch').addClass('form-control').css({
        width: '300px',
        'margin-left': '20px'
    });
    $('.dataTables_scrollBody').css({
        'border-top': '1px solid #ccc'
    });
});
