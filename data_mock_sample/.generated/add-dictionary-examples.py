import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
path = root / 'DATA-DICTIONARY.md'
original = path.read_text(encoding='utf-8')
samples = json.loads((root/'.generated/dictionary-samples.json').read_text(encoding='utf-8'))
read = lambda p: json.loads((root/p).read_text(encoding='utf-8'))
shopee = read('shopee-open-platform/raw/1001_orders.json')['payload']
lazada = read('lazada/raw/1001_orders.json')
laz_items = read('lazada/raw/1001_order_items.json')['payload']
shopify = read('shopify/raw/1001_orders.json')['payload']
supplement = read('shopee-open-platform/raw/1001_supplement.json')['payload']
manifest = read('manifest.json')
report = read('mart/validation-report.json')
contexts = [json.loads(line) for line in (root/'mart/agent-context.jsonl').read_text(encoding='utf-8').splitlines()]
issues = {c['issue_type']: c for c in contexts if c['shop_key']=='shopee-open-platform:1001'}

def excerpt(value, depth=0):
    if isinstance(value, list):
        return [excerpt(x,depth+1) for x in value[:1]]
    if isinstance(value, dict):
        return {k:excerpt(v,depth+1) for k,v in list(value.items())[:3]}
    return value

def cell(value, short=False):
    if short:
        value = excerpt(value)
    return '`' + json.dumps(value,ensure_ascii=False,separators=(', ', ': ')).replace('|','&#124;').replace('`','&#96;') + '`'

def get(value, dotted):
    for key in dotted.split('.'):
        array = key.endswith('[]')
        value = value[key[:-2] if array else key]
        if array:
            value = value[0]
    return value

conventions = {'shop_key':'lazada:1001','order_id':'100000','sku':'SHIRT-M',
    'source_document_id':'lazada/1001/orders','currency':'VND',
    'Money':'90000.00','NULL':None,'Timestamps':'2026-10-31T00:00:00+07:00',
    'Grain':{'shop_key':'lazada:1001','order_id':'100000'}}

def sample_for(section, label):
    fields = re.findall(r'`([^`]+)`',label)
    if section.startswith('## 2.'):
        return cell(conventions[fields[0] if fields else label])
    if section.startswith('### `raw.documents`'):
        return cell(lazada[fields[0]], True)
    if section == '### Shopee order payload':
        field = fields[0]
        if field.startswith('order_list'):
            field = 'response.'+field
        elif field.startswith('item_list'):
            field = 'response.order_list[].'+field
        return cell(get(shopee,field),True)
    if section == '### Lazada order and item payloads':
        field=fields[0]
        if label.startswith('Orders'):
            value=get(lazada,field)
        elif label.startswith('Items'):
            value=get({'payload':laz_items},field)
        elif field.startswith('orders'):
            value=get(lazada['payload']['data'],field)
        else:
            if field.startswith('data'):
                field='responses[].'+field
            value=get(laz_items,field)
        return cell(value,True)
    if section == '### Shopify order payload':
        field=fields[0]
        if field.startswith('payload'):
            value=get({'payload':shopify},field)
        elif field.startswith('orders'):
            value=get(shopify['data'],field)
        else:
            if field.startswith('lineItems'):
                field='nodes[].'+field
            value=get(shopify['data']['orders'],field)
        return cell(value,True)
    if section == '### Supplement payload, shared by all platforms':
        row=next(x for x in supplement['order_enrichment'] if x['promotion_id'])
    elif section.startswith('## 7.'):
        row=manifest
    else:
        table=re.search(r'`([^`]+)`',section).group(1)
        row=samples[table]
    if len(fields)>1:
        return '<br>'.join(f'`{key}`: {cell(get(row,key))}' for key in fields)
    return cell(get(row,fields[0]),True)

proposed = {
 'agent.issues':{'issue_id':'ISS-001','issue_key':issues['low_stock']['issue_key'],'shop_key':'shopee-open-platform:1001','status':'open','first_seen_at':'2026-10-31T00:00:00+07:00','last_seen_at':'2026-10-31T00:00:00+07:00','evidence_snapshot':{'available':2}},
 'agent.action_proposals':{'action_id':'ACT-001','issue_id':'ISS-001','action_type':'request_restock','parameters':{'sku':'SHIRT-M','units':50},'expected_impact':'Reduce stockout risk','cost_estimate':None,'risk':'Supplier may miss delivery date','reversible':False,'required_inputs':['supplier lead time','supplier quote']},
 'agent.approvals':{'approval_id':'APR-001','action_id':'ACT-001','seller_id':'SELLER-DEMO-001','selected_option':'request_restock','approved_at':'2026-10-31T00:10:00+07:00'},
 'agent.executions':{'execution_id':'EXE-001','action_id':'ACT-001','idempotency_key':'ACT-001:attempt-1','connector_target':'mock-supplier','before_state':{'request':None},'after_state':{'request':'REQ-001'},'tool_result':{'accepted':True},'status':'succeeded','rollback_parameters':None,'executed_at':'2026-10-31T00:11:00+07:00'},
 'agent.verifications':{'execution_id':'EXE-001','metric':'days_of_cover','baseline_value':0.21875,'baseline_window':'2026-10-24/2026-10-31','target':2,'post_action_window':'2026-10-31/2026-11-02','minimum_sample':1,'measured_value':None,'outcome':'waiting'},
 'agent.trust':{'shop_key':'shopee-open-platform:1001','issue_type':'low_stock','action_type':'request_restock','observed_outcomes':[],'seller_policy':'Require approval for purchases','automation_mode':'suggest_only'}
}

lines=original.splitlines()
out=[]
section=''
mode=None
row_count=0
for line in lines:
    if line.startswith('#'):
        section=line
    if not line.startswith('|'):
        mode=None
        out.append(line)
        continue
    columns=[x.strip() for x in line.strip('|').split('|')]
    if columns[0].startswith('Field'):
        mode='field'
        out.append(line[:-1]+' Example |')
    elif columns[0]=='Issue type':
        mode='metrics'
        out.append(line[:-1]+' Example metrics |')
    elif columns[0]=='Proposed table':
        mode='proposed'
        out.append(line[:-1]+' Illustrative example (not stored) |')
    elif mode and all(re.fullmatch(r':?-+:?',x) for x in columns):
        out.append(line+'---|')
    elif mode:
        if mode=='field':
            example=sample_for(section,columns[0])
        elif mode=='metrics':
            example=cell(issues[columns[0].strip('`')]['metrics'])
        else:
            example=cell(proposed[columns[0].strip('`')])
        out.append(line[:-1]+' '+example+' |')
        row_count+=1
    else:
        out.append(line)

updated='\n'.join(out)+'\n'
intro='''
The **Example** columns use values from the generated fixtures and queried SQL views. Examples are JSON-style: quoted strings, unquoted numbers/booleans, and `null` for missing values. Money returned as a decimal string remains quoted. Nested JSON/array examples are shortened excerpts (the first item and selected keys), not complete records. Samples are consistent within each table, but different tables may illustrate different shops, dates or orders. Future `agent.*` records are explicitly illustrative and are not stored in the dataset.
'''
needle='For API references and confidence levels, see [SOURCES.md](SOURCES.md).\n'
updated=updated.replace(needle,needle+intro,1)

# Give each capability a concrete value, rather than leaving nested fields only in prose.
needle='The map is partial; an absent capability key does not establish support.\n'
cap=samples['core.shops']['capabilities']
cap_descriptions={'orders':'Order connector data status.','reviews':'Source of customer-review data.',
 'finance':'Source of fee/payout summaries.','inventory':'Source of stock observations.',
 'costs':'Provenance of merchant product costs.','account_health':'Availability of account-health events.'}
table='\n| Field | Meaning | Example |\n|---|---|---|\n'
for key,value in cap.items():
    table+=f'| `capabilities.{key}` | {cap_descriptions[key]} | {cell(value)} |\n'
table+='\nFor the Shopify shop, `capabilities.account_health` is `"unsupported"`.\n'
updated=updated.replace(needle,needle+table,1)

# Evidence container examples cover nested IDs, descriptions and dates as well.
start=updated.index('The different evidence shapes are intentional in this prototype:')
end=updated.index('### Detection thresholds actually in the SQL',start)
evidence='The different evidence shapes are intentional in this prototype. Array samples show the first element.\n\n'
evidence+='| Evidence type | Included fields / purpose | Example |\n|---|---|---|\n'
for name,kind,description in [
 ('Reviews','product_reviews','Review ID, text, rating and raw source.'),
 ('Promotion','promotion_loss','Order ID, margin and order/finance sources.'),
 ('Cancellation','cancellation_spike','Relation and shop for drill-down using packet windows.'),
 ('Returns','return_spike','Relation and shop for drill-down using packet windows.'),
 ('Fees','fee_spike','Relation and shop for drill-down using packet windows.'),
 ('Payout','payout_mismatch','Order ID and settlement source.'),
 ('Inventory','low_stock','Raw document IDs supporting stock.'),
 ('Shipping','shipment_risk','Order ID, deadline, policy basis and source.'),
 ('Health','account_health','Event ID, reason and source.')]:
    value=issues[kind]['evidence']
    if isinstance(value,list): value=value[:1]
    evidence+=f'| {name} | {description} | {cell(value)} |\n'
updated=updated[:start]+evidence+'\n'+updated[end:]

# The validation report was previously described only inline.
needle='It is a test report, not seller-facing evidence.\n'
descriptions={'engine':'PostgreSQL build used to validate the SQL.','checks':'Number of PostgreSQL assertions.',
 'orders':'Loaded order count.','order_lines':'Loaded item-line count.',
 'issue_candidates':'Exported candidate count.','counts':'Breakdown by shop and issue type.'}
table='\n| Field | Meaning | Example |\n|---|---|---|\n'
for key,description in descriptions.items():
    value=report[key]
    if isinstance(value,list): value=value[:1]
    table+=f'| `{key}` | {description} | {cell(value)} |\n'
for key,description in [('shop_key','Shop in this count group.'),('issue_type','Issue category in this group.'),('count','Number of candidates in this group.')]:
    table+=f'| `counts[].{key}` | {description} | {cell(report["counts"][0][key])} |\n'
updated=updated.replace(needle,needle+table,1)
path.write_text(updated,encoding='utf-8')
print(f'Added example cells for {row_count} existing field/metric/proposed-table rows, plus capability, evidence and validation-report tables.')
