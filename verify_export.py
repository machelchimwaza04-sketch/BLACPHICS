import json
from collections import defaultdict

# Load and analyze the exported data
with open('full_data_export.json', 'r') as f:
    data = json.load(f)

print(f'Total records exported: {len(data)}\n')

# Breakdown by model
models = defaultdict(int)
for item in data:
    models[item['model']] += 1

print('Breakdown by model:')
for model, count in sorted(models.items()):
    print(f'  {model}: {count}')

# Check specific tables from requirements
print('\n\nCRITICAL TABLES VERIFICATION:')
critical_models = {
    'branches.branch': 5,
    'customers.customer': 100,
    'products.product': 250,
    'products.productvariant': 503,
    'orders.order': 67,
    'orders.orderitem': 25,
    'auth.user': 1,
}

for model, expected in critical_models.items():
    actual = models.get(model, 0)
    status = '✅' if actual == expected else '❌'
    print(f'  {status} {model}: {actual} rows (expected {expected})')
