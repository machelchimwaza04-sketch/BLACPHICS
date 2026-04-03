from rest_framework import serializers
from .models import Category, Product, ProductVariant


# =========================================================
# CATEGORY
# =========================================================
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


# =========================================================
# PRODUCT VARIANT
# =========================================================
class ProductVariantSerializer(serializers.ModelSerializer):

    # 🔥 Inventory Intelligence
    stock_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()

    # 🔥 Pricing Intelligence
    final_selling_price = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = '__all__'


# =========================================================
# PRODUCT
# =========================================================
class ProductSerializer(serializers.ModelSerializer):

    variants = ProductVariantSerializer(many=True, read_only=True)

    # 🔥 Aggregated Intelligence
    total_stock = serializers.SerializerMethodField()
    total_available = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()

    # Optional existing fields (safe fallback)
    is_low_stock = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = Product
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