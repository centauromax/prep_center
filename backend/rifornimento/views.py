from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum, F
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Product, RifornimentoRequest, RifornimentoItem
import logging

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Dashboard principale dell'app Rifornimento"""
    try:
        # Statistiche prodotti
        total_products = Product.objects.filter(is_active=True).count()
        products_need_restocking = Product.objects.filter(
            is_active=True,
            current_stock__lte=F('minimum_stock')
        ).count()
        
        # Statistiche richieste rifornimento
        pending_requests = RifornimentoRequest.objects.filter(
            status__in=['draft', 'pending', 'approved']
        ).count()
        overdue_requests = RifornimentoRequest.objects.filter(
            needed_by__lt=timezone.now().date(),
            status__in=['draft', 'pending', 'approved', 'ordered', 'shipped']
        ).count()
        
        # Prodotti con stock basso (da rifornire)
        low_stock_products = Product.objects.filter(
            is_active=True,
            current_stock__lte=F('minimum_stock')
        ).order_by('current_stock')[:10]
        
        # Richieste recenti
        recent_requests = RifornimentoRequest.objects.order_by('-created_at')[:5]
        
        context = {
            'total_products': total_products,
            'products_need_restocking': products_need_restocking,
            'pending_requests': pending_requests,
            'overdue_requests': overdue_requests,
            'low_stock_products': low_stock_products,
            'recent_requests': recent_requests,
        }
        
        return render(request, 'rifornimento/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Errore nella dashboard rifornimenti: {e}")
        messages.error(request, f"Errore nel caricamento della dashboard: {e}")
        return render(request, 'rifornimento/dashboard.html', {'error': str(e)})


@login_required
def product_list(request):
    """Lista prodotti con filtri e ricerca"""
    try:
        products = Product.objects.filter(is_active=True)
        
        # Filtri
        search = request.GET.get('search', '')
        brand_filter = request.GET.get('brand', '')
        stock_filter = request.GET.get('stock', '')  # 'low', 'ok', 'all'
        
        if search:
            products = products.filter(
                Q(sku__icontains=search) |
                Q(title__icontains=search) |
                Q(asin__icontains=search) |
                Q(fnsku__icontains=search) |
                Q(brand__icontains=search)
            )
        
        if brand_filter:
            products = products.filter(brand__icontains=brand_filter)
        
        if stock_filter == 'low':
            products = products.filter(current_stock__lte=F('minimum_stock'))
        elif stock_filter == 'ok':
            products = products.filter(current_stock__gt=F('minimum_stock'))
        
        # Ordinamento
        sort_by = request.GET.get('sort', 'brand')
        if sort_by in ['brand', 'title', 'current_stock', 'minimum_stock', 'sales_velocity']:
            if sort_by == 'current_stock':
                products = products.order_by('current_stock', 'brand')
            else:
                products = products.order_by(sort_by)
        
        # Paginazione
        paginator = Paginator(products, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Brands per filtro
        brands = Product.objects.filter(is_active=True).values_list('brand', flat=True).distinct().order_by('brand')
        
        context = {
            'page_obj': page_obj,
            'search': search,
            'brand_filter': brand_filter,
            'stock_filter': stock_filter,
            'sort_by': sort_by,
            'brands': brands,
        }
        
        return render(request, 'rifornimento/product_list.html', context)
        
    except Exception as e:
        logger.error(f"Errore nella lista prodotti: {e}")
        messages.error(request, f"Errore nel caricamento prodotti: {e}")
        return render(request, 'rifornimento/product_list.html', {'error': str(e)})


@login_required
def request_list(request):
    """Lista richieste di rifornimento"""
    try:
        requests = RifornimentoRequest.objects.all()
        
        # Filtri
        status_filter = request.GET.get('status', '')
        priority_filter = request.GET.get('priority', '')
        search = request.GET.get('search', '')
        
        if status_filter:
            requests = requests.filter(status=status_filter)
        
        if priority_filter:
            requests = requests.filter(priority=priority_filter)
        
        if search:
            requests = requests.filter(
                Q(request_number__icontains=search) |
                Q(title__icontains=search) |
                Q(supplier__icontains=search)
            )
        
        # Ordinamento
        sort_by = request.GET.get('sort', '-created_at')
        requests = requests.order_by(sort_by)
        
        # Paginazione
        paginator = Paginator(requests, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'status_filter': status_filter,
            'priority_filter': priority_filter,
            'search': search,
            'sort_by': sort_by,
            'status_choices': RifornimentoRequest.STATUS_CHOICES,
            'priority_choices': RifornimentoRequest.PRIORITY_CHOICES,
        }
        
        return render(request, 'rifornimento/request_list.html', context)
        
    except Exception as e:
        logger.error(f"Errore nella lista richieste: {e}")
        messages.error(request, f"Errore nel caricamento richieste: {e}")
        return render(request, 'rifornimento/request_list.html', {'error': str(e)})


@login_required
def request_detail(request, request_id):
    """Dettaglio richiesta di rifornimento"""
    try:
        rifornimento_request = get_object_or_404(RifornimentoRequest, id=request_id)
        items = rifornimento_request.items.all().select_related('product')
        
        context = {
            'request': rifornimento_request,
            'items': items,
        }
        
        return render(request, 'rifornimento/request_detail.html', context)
        
    except Exception as e:
        logger.error(f"Errore nel dettaglio richiesta {request_id}: {e}")
        messages.error(request, f"Errore nel caricamento richiesta: {e}")
        return redirect('rifornimento:request_list')


# =============================================================================
# API ENDPOINTS
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def api_dashboard_stats(request):
    """API endpoint per statistiche dashboard"""
    try:
        from django.db.models import F
        
        # Statistiche prodotti
        total_products = Product.objects.filter(is_active=True).count()
        products_need_restocking = Product.objects.filter(
            is_active=True,
            current_stock__lte=F('minimum_stock')
        ).count()
        
        # Statistiche richieste
        total_requests = RifornimentoRequest.objects.count()
        pending_requests = RifornimentoRequest.objects.filter(
            status__in=['draft', 'pending', 'approved']
        ).count()
        
        active_requests = RifornimentoRequest.objects.filter(
            status__in=['approved', 'ordered', 'shipped']
        ).count()
        
        overdue_requests = RifornimentoRequest.objects.filter(
            needed_by__lt=timezone.now().date(),
            status__in=['draft', 'pending', 'approved', 'ordered', 'shipped']
        ).count()
        
        # Statistiche per status
        status_stats = {}
        for status_code, status_name in RifornimentoRequest.STATUS_CHOICES:
            count = RifornimentoRequest.objects.filter(status=status_code).count()
            status_stats[status_code] = {
                'name': status_name,
                'count': count
            }
        
        return Response({
            'success': True,
            'data': {
                'products': {
                    'total': total_products,
                    'need_restocking': products_need_restocking,
                    'restocking_percentage': round((products_need_restocking / total_products * 100), 1) if total_products > 0 else 0
                },
                'requests': {
                    'total': total_requests,
                    'pending': pending_requests,
                    'active': active_requests,
                    'overdue': overdue_requests
                },
                'status_breakdown': status_stats
            }
        })
        
    except Exception as e:
        logger.error(f"Errore API dashboard stats: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_products_low_stock(request):
    """API endpoint per prodotti con stock basso"""
    try:
        from django.db.models import F
        
        limit = int(request.GET.get('limit', 20))
        
        products = Product.objects.filter(
            is_active=True,
            current_stock__lte=F('minimum_stock')
        ).order_by('current_stock')[:limit]
        
        data = []
        for product in products:
            data.append({
                'id': product.id,
                'sku': product.sku,
                'title': product.title,
                'brand': product.brand,
                'current_stock': product.current_stock,
                'minimum_stock': product.minimum_stock,
                'suggested_quantity': product.suggested_order_quantity,
                'days_coverage': product.days_of_inventory,
                'sales_velocity': float(product.sales_velocity) if product.sales_velocity else 0
            })
        
        return Response({
            'success': True,
            'data': data,
            'total_found': len(data)
        })
        
    except Exception as e:
        logger.error(f"Errore API products low stock: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_create_request_from_products(request):
    """API endpoint per creare richiesta di rifornimento da lista prodotti"""
    try:
        data = request.data
        
        # Validazione dati
        title = data.get('title')
        priority = data.get('priority', 'normal')
        needed_by = data.get('needed_by')
        product_quantities = data.get('products', [])  # [{'product_id': 1, 'quantity': 50}, ...]
        
        if not title:
            return Response({
                'success': False,
                'error': 'Titolo richiesta obbligatorio'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not product_quantities:
            return Response({
                'success': False,
                'error': 'Almeno un prodotto è obbligatorio'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Crea richiesta
        rifornimento_request = RifornimentoRequest.objects.create(
            title=title,
            priority=priority,
            needed_by=needed_by,
            requested_by=request.user if request.user.is_authenticated else None,
            notes=data.get('notes', '')
        )
        
        # Crea elementi
        items_created = 0
        for item_data in product_quantities:
            try:
                product = Product.objects.get(id=item_data['product_id'])
                quantity = int(item_data['quantity'])
                
                RifornimentoItem.objects.create(
                    request=rifornimento_request,
                    product=product,
                    quantity=quantity,
                    reason=item_data.get('reason', f'Stock basso: {product.current_stock} <= {product.minimum_stock}')
                )
                items_created += 1
                
            except Product.DoesNotExist:
                logger.warning(f"Prodotto {item_data['product_id']} non trovato")
                continue
            except (ValueError, KeyError) as e:
                logger.warning(f"Dati item non validi: {e}")
                continue
        
        return Response({
            'success': True,
            'data': {
                'request_id': rifornimento_request.id,
                'request_number': rifornimento_request.request_number,
                'items_created': items_created,
                'total_quantity': rifornimento_request.total_quantity
            }
        })
        
    except Exception as e:
        logger.error(f"Errore API create request: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
