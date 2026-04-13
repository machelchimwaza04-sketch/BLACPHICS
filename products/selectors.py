from django.db.models import Prefetch

from products.models import Category, Product, ProductVariant, CustomizationService


def products_for_branch(branch_id):
    return (
        Product.objects.filter(branch_id=branch_id)
        .select_related('branch', 'category')
        .prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.order_by('size', 'color'))
        )
        .order_by('name')
    )


def product_detail_selector(product_id):
    return (
        Product.objects.filter(pk=product_id)
        .select_related('branch', 'category')
        .prefetch_related('variants')
        .first()
    )


def categories_all():
    return Category.objects.all().order_by('name')


def customization_services_active():
    return CustomizationService.objects.filter(is_active=True).order_by('name')
