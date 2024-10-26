:root {
    --primary-color: #007ea7;
    --secondary-color: #219ebc;
    --accent-color: #8ecae6;
    --light-color: #f8f9fa;
    --dark-color: #023047;
    --text-color: #333333;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: var(--text-color);
    line-height: 1.6;
}

/* Navbar */
.custom-navbar {
    background-color: var(--primary-color);
    padding: 1rem 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.navbar-brand {
    color: white !important;
    display: flex;
    align-items: center;
    gap: 1rem;
}

.brand-text {
    font-size: 1.5rem;
    font-weight: 600;
}

.language-switcher select {
    background-color: transparent;
    color: white;
    border: 1px solid rgba(255,255,255,0.5);
    padding: 0.375rem 0.75rem;
    border-radius: 4px;
}

.language-switcher select option {
    background-color: var(--primary-color);
    color: white;
}

/* Main Content */
.main-content {
    padding: 2rem 0;
}

section {
    margin-bottom: 2rem;
}

/* Introduction Section */
.intro-section {
    text-align: center;
    padding: 3rem 0;
}

.intro-section h1 {
    color: var(--primary-color);
    margin-bottom: 1.5rem;
}

/* Cards */
.card {
    border: none;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    margin-bottom: 2rem;
}

.card-body {
    padding: 2rem;
}

/* Upload Section */
.upload-section .card {
    background-color: var(--light-color);
}

.upload-area {
    padding: 2rem;
    border: 2px dashed var(--secondary-color);
    border-radius: 8px;
    text-align: center;
}

/* Buttons */
.btn-primary {
    background-color: var(--primary-color);
    border-color: var(--primary-color);
    padding: 0.5rem 2rem;
    border-radius: 5px;
    transition: all 0.3s ease;
}

.btn-primary:hover {
    background-color: var(--secondary-color);
    border-color: var(--secondary-color);
}

/* Results Section */
.results-section .card {
    background-color: var(--accent-color);
    color: var(--dark-color);
}

/* Info Sections */
.info-section {
    background-color: white;
    padding: 2rem;
    border-radius: 10px;
    height: 100%;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.info-section h3 {
    color: var(--secondary-color);
    margin-bottom: 1rem;
}

/* DataTables Customization */
.datatable-section .card {
    overflow: hidden;
}

table.dataTable {
    width: 100% !important;
    margin-bottom: 1rem;
    color: var(--text-color);
}

.dataTables_wrapper .dataTables_paginate .paginate_button.current {
    background: var(--primary-color) !important;
    color: white !important;
    border: 1px solid var(--primary-color) !important;
}

.dataTables_wrapper .dataTables_paginate .paginate_button:hover {
    background: var(--secondary-color) !important;
    color: white !important;
    border: 1px solid var(--secondary-color) !important;
}

/* Responsive Design */
@media (max-width: 768px) {
    .info-sections .col-md-6 {
        margin-bottom: 1rem;
    }
    
    .card-body {
        padding: 1rem;
    }
}
