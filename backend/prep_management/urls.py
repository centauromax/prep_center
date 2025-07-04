from django.urls import path
from . import views
import logging

logger = logging.getLogger('prep_management')
logger.info('[prep_management.urls] File urls.py caricato')

urlpatterns = [
    path('', views.index, name='index'),
    path('api/open-shipments/', views.open_shipments, name='open_shipments'),
    path('merchants/', views.merchants_list, name='merchants_list'),
    path('api-debug/', views.api_config_debug, name='api_config_debug'),
    path('webhook/', views.shipment_status_webhook, name='shipment_status_webhook'),
    path('test-webhook/', views.test_webhook, name='test_webhook'),
    path('shipment-updates/', views.shipment_status_updates, name='shipment_status_updates'),
    path('webhook/manage/', views.manage_webhooks, name='manage_webhooks'),
    path('queue/push/', views.push_outgoing_message, name='push_outgoing_message'),
    path('queue/poll/', views.poll_outgoing_messages, name='poll_outgoing_messages'),
    path('queue/consume/<int:pk>/', views.push_outgoing_message, name='consume_outgoing_message'),
    path('queue/receive/', views.receive_extension_message, name='receive_extension_message'),
    path('queue/wait/', views.wait_for_extension_response, name='wait_for_extension_response'),
    path('search-shipments/', views.search_shipments_by_products, name='search_shipments_by_products'),
    path('test-outbound-without-inbound/', views.test_outbound_without_inbound, name='test_outbound_without_inbound'),
    
    # URL per il bot Telegram
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
    path('telegram/bot-info/', views.telegram_bot_info, name='telegram_bot_info'),
    path('telegram/set-webhook/', views.set_telegram_webhook, name='set_telegram_webhook'),
    path('telegram/debug/', views.telegram_debug, name='telegram_debug'),
    path('telegram/merchants-debug/', views.telegram_merchants_debug, name='telegram_merchants_debug'),
    path('telegram/admin-debug/', views.telegram_admin_debug, name='telegram_admin_debug'),
    path('telegram/test-multiple-admin/', views.test_multiple_admin_notification, name='test_multiple_admin'),
    path('telegram/users-debug/', views.telegram_users_debug, name='telegram_users_debug'),
    path('telegram/test-email-normalization/', views.test_email_normalization, name='test_email_normalization'),
    
    # URL per creare admin
    path('create-admin/', views.create_admin_user, name='create_admin_user'),

    # Endpoint di test e debug esistenti
    path('api/telegram/admin-debug/', views.telegram_admin_debug, name='admin_debug'),
    path('api/telegram/users-debug/', views.telegram_users_debug, name='users_debug'),
    path('api/telegram/test-multiple-admin/', views.test_multiple_admin_notification, name='test_multiple_admin'),
    path('api/telegram/test-email-normalization/', views.test_email_normalization, name='test_email_normalization'),
    
    # Endpoint per test conteggio prodotti
    path('api/telegram/test-outbound-closed-products/', views.test_outbound_closed_with_products, name='test_outbound_closed_products'),
    path('api/telegram/test-outbound-closed-products-full/', views.test_outbound_closed_with_products, name='test_outbound_closed_products_full'),
    path('api/telegram/test-outbound-created-with-name/', views.test_outbound_created_with_name, name='test_outbound_created_with_name'),
    path('api/test-client-get-shipments/', views.test_client_get_shipments, name='test_client_get_shipments'),
    path('api/test-client-detailed/', views.test_client_detailed, name='test_client_detailed'),
    path('api/telegram/test-inbound-received/', views.test_inbound_received_notification, name='test_inbound_received'),
    path('api/telegram/test-inbound-received-more/', views.test_inbound_received_more, name='test_inbound_received_more'),
    path('api/telegram/test-inbound-received-less/', views.test_inbound_received_less, name='test_inbound_received_less'),
    path('api/test-residual-inbound/', views.test_residual_inbound_creation, name='test_residual_inbound_creation'),
    path('api/test-residual-logic/', views.test_residual_logic_simple, name='test_residual_logic_simple'),
    path('api/test-residual-version/', views.test_residual_version, name='test_residual_version'),
    path('api/test-partial-inbound/', views.test_partial_inbound_creation, name='test_partial_inbound_creation'),
    path('api/test-partial-only/', views.test_partial_only_creation, name='test_partial_only_creation'),
    path('version-file/', views.version_file, name='version_file'),

    path('api/test-outbound-closed-test2/', views.test_outbound_closed_test2, name='test_outbound_closed_test2'),
    path('api/debug-test2-payload/', views.debug_test2_payload, name='debug_test2_payload'),
    path('api/debug-latest-test2-raw/', views.debug_latest_test2_raw, name='debug_latest_test2_raw'),
    path('api/reprocess-update/<int:update_id>/', views.reprocess_webhook_update, name='reprocess_webhook_update'),

    # Debug endpoints  
    # path('telegram/debug/', views.telegram_debug_view, name='telegram_debug'),  # Disabilitato - duplicato
    path('debug/webhook/<int:update_id>/', views.debug_webhook_payload, name='debug_webhook_payload'),
    path('debug/webhook-processor/', views.debug_webhook_processor, name='debug_webhook_processor'),
    path('debug/payload/<int:update_id>/', views.debug_webhook_payload_simple, name='debug_webhook_payload_simple'),
    path('debug/reprocess/<int:update_id>/', views.reprocess_webhook_for_debug, name='reprocess_webhook_for_debug'),

    # 🆕 Test endpoints
    path('test_outbound_closed_process/', views.test_outbound_closed_process, name='test_outbound_closed_process'),  # 🆕 Test processo outbound closed
    path('debug_last_update/', views.debug_last_update, name='debug_last_update'),  # 🆕 Debug ultimo update processato
    path('debug_api_steps/', views.debug_api_steps, name='debug_api_steps'),  # 🆕 Debug API steps
    path('test_partial_submit/', views.test_partial_submit, name='test_partial_submit'),  # 🆕 Test submit spedizioni PARTIAL
    path('test_manual_submit/', views.test_manual_submit, name='test_manual_submit'),  # 🆕 Test submit manuale shipment
    
    # 🚀 Amazon SP-API endpoints
    path('sp-api/config/', views.sp_api_config_list, name='sp_api_config_list'),
    path('sp-api/test/<int:config_id>/', views.sp_api_test_connection, name='sp_api_test_connection'),
    path('sp-api/test-lwa/<int:config_id>/', views.sp_api_test_lwa_only, name='sp_api_test_lwa_only'),
    path('sp-api/test-raw/<int:config_id>/', views.sp_api_test_raw_call, name='sp_api_test_raw_call'),
    path('sp-api/debug-advanced/<int:config_id>/', views.sp_api_debug_advanced, name='sp_api_debug_advanced'),
    path('sp-api/diagnostic/<int:config_id>/', views.sp_api_diagnostic_test, name='sp_api_diagnostic_test'),
    path('sp-api/create-us-test/', views.sp_api_create_us_test_config, name='sp_api_create_us_test_config'),
    path('sp-api/authorization-status/', views.sp_api_authorization_status, name='sp_api_authorization_status'),
    path('sp-api/orders/', views.sp_api_orders_list, name='sp_api_orders_list'),
    path('sp-api/orders/<str:order_id>/', views.sp_api_order_detail, name='sp_api_order_detail'),
    path('sp-api/inventory/', views.sp_api_inventory_summary, name='sp_api_inventory_summary'),
    path('sp-api/reports/', views.sp_api_reports_list, name='sp_api_reports_list'),
    path('sp-api/reports/create/', views.sp_api_create_report, name='sp_api_create_report'),
    path('sp-api/account/', views.sp_api_account_info, name='sp_api_account_info'),
    path('sp-api/test-orders/', views.sp_api_test_orders_page, name='sp_api_test_orders_page'),
    path('sp-api/debug-aws-fields/', views.debug_aws_fields, name='debug_aws_fields'),
    
    # 🚀 SP-API Sales Analysis endpoints
    path('sp-api/sales-analysis/', views.sp_api_sales_analysis_page, name='sp_api_sales_analysis_page'),
    path('sp-api/sales-analysis/data/', views.sp_api_sales_analysis_data, name='sp_api_sales_analysis_data'),
    
    # 🔧 Endpoint temporaneo per fix marketplace_id
    path('sp-api/update-marketplace-id/', views.update_marketplace_id_endpoint, name='update_marketplace_id_endpoint'),
]
