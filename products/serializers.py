from rest_framework import serializers
from .models import Category, Product, ProductVariant, CustomizationService


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ProductVariantSerializer(serializers.ModelSerializer):
    stock_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    is_low_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = '__all__'


class CustomizationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomizationService
        fields = '__all__'

    # =========================
    # AGGREGATIONS
    # =========================
    def get_total_stock(self, obj):
        return sum(v.stock_quantity for v in obj.variants.all())

    def get_total_available(self, obj):
        return sum(v.available_quantity for v in obj.variants.all())

    def get_stock_status(self, obj):
        variants = obj.variants.all()

        if not variants:
            return 'out_of_stock'

        if any(v.available_quantity > 5 for v in variants):
            return 'in_stock'

        if any(v.available_quantity > 0 for v in variants):
            return 'low_stock'

        return 'out_of_stock'