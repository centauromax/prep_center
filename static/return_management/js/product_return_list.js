$(document).ready(function() {
    var table = $('#productTable').DataTable({
        paging: true,
        pageLength: 500,
        lengthChange: false,
        searching: true,
        scrollY: 'calc(100vh - 300px)', // Adjust based on header/footer height
        scrollX: true,
        scrollCollapse: true,
        fixedHeader: true,
        language: {
            paginate: {
                next: 'Next',
                previous: 'Previous'
            },
            info: 'Showing _START_ to _END_ of _TOTAL_ entries'
        },
        drawCallback: function(settings) {
            // Update the info text dynamically
            var info = this.api().page.info();
            $('#tableInfo').html(
                'Showing ' + (info.start + 1) + ' to ' + info.end + ' of ' + info.recordsTotal + ' entries'
            );

            // Move pagination to custom footer
            $('#tablePagination').html($(this.api().table().container()).find('.dataTables_paginate'));
        },
        initComplete: function() {
            // Apply column-specific search
            this.api().columns().every(function() {
                var column = this;
                $('input', column.header()).on('keyup change clear', function() {
                    if (column.search() !== this.value) {
                        column.search(this.value).draw();
                    }
                });
            });
        }
    });

    // Global search
    $('#globalSearch').on('keyup', function() {
        table.search(this.value).draw();
    });
});


