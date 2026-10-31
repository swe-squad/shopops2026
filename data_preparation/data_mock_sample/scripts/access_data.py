"""Application-owned demo access fixtures; never inferred from marketplace payloads."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS_KEYS = {'users': ['user_id'], 'merchants': ['merchant_id'],
               'merchant_memberships': ['user_id', 'merchant_id']}


def load_access():
    return {table: [json.loads(line) for line in (ROOT/'access'/f'{table}.jsonl')
                   .read_text(encoding='utf-8').splitlines() if line.strip()]
            for table in (*ACCESS_KEYS, 'shop_ownership')}


def merchant_for_shop(platform, shop_id):
    fixtures = load_access()
    owners = [row['merchant_id'] for row in fixtures['shop_ownership']
              if row['shop_key'] == f'{platform}:{shop_id}']
    if len(owners) != 1 or owners[0] not in {row['merchant_id'] for row in fixtures['merchants']}:
        raise ValueError('Missing, duplicate or unknown merchant ownership for shop')
    return owners[0]
