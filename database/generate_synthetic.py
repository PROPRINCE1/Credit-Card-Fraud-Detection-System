"""Create reproducible CSV files, without connecting to any database."""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.synthetic import synthetic_data, FEATURES

DEFAULT_OUTPUT = ROOT / 'database' / 'generated'

def generate(customers=200, transactions=20000, seed=2026, end_date='2026-10-29'):
    if customers < 1 or transactions < customers:
        raise ValueError('Require at least one transaction per customer')
    end = datetime.fromisoformat(end_date).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=90)
    rng = np.random.default_rng(seed)
    people = []
    first = ['Ayaan','Sara','Umer','Hina','Ali','Noor','Bilal','Mariam','Zain','Ayesha']
    last = ['Khan','Ahmed','Pervez','Siddiqui','Malik','Shah','Iqbal','Raza']
    homes = ['Karachi','Lahore','Islamabad','Multan','Peshawar']
    medians = rng.uniform(25, 180, customers)
    for i in range(1, customers + 1):
        people.append({'id':i, 'name':f'{first[(i-1)%len(first)]} {last[(i-1)//len(first)%len(last)]} (Demo {i:03d})',
                       'email':f'customer{i:03d}@example.com',
                       'created_at':(start-timedelta(days=int(rng.integers(1,366)))).isoformat()})
    features = synthetic_data(transactions, seed)
    owners = np.concatenate([np.arange(1, customers+1), rng.integers(1, customers+1, transactions-customers)])
    rng.shuffle(owners)
    times = np.sort(rng.integers(0, 90*86400, transactions))
    shops = [('Fresh Basket','Groceries'),('Cloud Tech','Electronics'),('City Wear','Clothing'),
             ('Sky Tickets','Travel'),('Care Pharmacy','Healthcare'),('Daily Market','Other')]
    records=[]
    for i, row in enumerate(features.to_dict('records')):
        customer_id=int(owners[i]); stamp=start+timedelta(seconds=int(times[i]))
        merchant,category=shops[int(rng.integers(len(shops)))]
        # Approximate demo distance features, not a real geospatial travel model.
        location=homes[(customer_id-1)%len(homes)] if row['distance_from_home']<100 else 'Away / simulated travel'
        if row['online_order']: location='Online'
        record={'id':i+1,'customer_id':customer_id,
                'amount':round(float(medians[customer_id-1]*row['ratio_to_median_purchase_price']),2),
                'merchant':merchant,'category':category,'location':location,
                'hour':stamp.hour,'created_at':stamp.isoformat()}
        record.update({key:round(float(row[key]),6) if key.startswith(('distance','ratio')) else bool(row[key]) for key in FEATURES})
        # Ground truth remains in CSV only: existing database schema is preserved.
        record['synthetic_fraud_label']=int(row['fraud'])
        records.append(record)
    return pd.DataFrame(people),pd.DataFrame(records)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--customers',type=int,default=200)
    parser.add_argument('--transactions',type=int,default=20000)
    parser.add_argument('--seed',type=int,default=2026)
    parser.add_argument('--end-date',default='2026-10-29',help='Exclusive UTC date; fixed default for reproducibility')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    customers,transactions=generate(args.customers,args.transactions,args.seed,args.end_date)
    args.output.mkdir(parents=True,exist_ok=True)
    customers.to_csv(args.output/'customers.csv',index=False)
    transactions.to_csv(args.output/'transactions.csv',index=False)
    info={'customers':len(customers),'transactions':len(transactions),'seed':args.seed,
          'end_date_exclusive':args.end_date,'days':90,'synthetic_fraud_labels':int(transactions.synthetic_fraud_label.sum()),
          'note':'Synthetic labels are not predictions. Predictions and alerts are computed during seeding.'}
    (args.output/'manifest.json').write_text(json.dumps(info,indent=2))
    print(json.dumps(info,indent=2))
if __name__=='__main__':main()
