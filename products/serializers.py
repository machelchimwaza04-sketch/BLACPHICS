from rest_framework import serializers
from .models import Category, Product, ProductVariant, CustomizationService


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ProductVariantSerializer(serializers.ModelSerializer):
    stock_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    selling_price = serializers.ReadOnlyField()
    gross_margin = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    is_low_stock = serializers.ReadOnlyField()
    total_stock = serializers.SerializerMethodField()
    total_available = serializers.SerializerMethodField()
    overall_stock_status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = '__all__'

    def get_total_stock(self, obj):
        return sum(v.stock_quantity for v in obj.variants.all())

    def get_total_available(self, obj):
        return sum(v.available_quantity for v in obj.variants.all())

    def get_overall_stock_status(self, obj):
        variants = obj.variants.all()
        if not variants:
            return 'out_of_stock'
        if any(v.available_quantity > (obj.low_stock_threshold or 5) for v in variants):
            return 'in_stock'
        if any(v.available_quantity > 0 for v in variants):
            return 'low_stock'
        return 'out_of_stock'


class CustomizationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomizationService
        fields = '__all__'