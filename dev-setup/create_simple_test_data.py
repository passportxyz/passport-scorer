#!/usr/bin/env python
"""Create simple test data for utility endpoints"""
import os, sys, django
from decimal import Decimal
from datetime import timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
api_path = os.path.join(project_root, 'api')
sys.path.insert(0, api_path)

env_file = os.path.join(project_root, '.env.development')
if os.path.exists(env_file):
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scorer.settings')
django.setup()

from account.models import AddressList, AddressListMember
from ceramic_cache.models import Ban
from stake.models import Stake
from django.utils import timezone

TEST_ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Allow list
test_list, _ = AddressList.objects.get_or_create(name='testlist')
AddressListMember.objects.get_or_create(list=test_list, address=TEST_ADDRESS.lower())
print(f"✓ Allow list: {TEST_ADDRESS} in 'testlist'")

# Ban
Ban.objects.get_or_create(address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", type='account', defaults={'end_time': timezone.now() + timedelta(days=30)})
print("✓ Ban: Active ban created")

# Stakes  
Stake.objects.get_or_create(chain=1, staker=TEST_ADDRESS.lower(), stakee=TEST_ADDRESS.lower(), defaults={'lock_time': timezone.now() - timedelta(days=30), 'unlock_time': timezone.now() + timedelta(days=60), 'last_updated_in_block': 12345678, 'current_amount': Decimal('1000.50')})
print(f"✓ Stake: {TEST_ADDRESS} has 1000.50 GTC")

print("\nDone! Run comparison tests with realistic data.")
