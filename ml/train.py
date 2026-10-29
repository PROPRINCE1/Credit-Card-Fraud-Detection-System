"""Train on a SYNTHETIC DEMO dataset, not real card data.
Replace dataset generation with a legally usable, matching-feature labeled dataset
before making real-world claims. Synthetic metrics do not establish real fraud accuracy.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score,recall_score,f1_score,average_precision_score,confusion_matrix,accuracy_score,roc_auc_score
from sklearn.model_selection import train_test_split

ROOT=Path(__file__).resolve().parent
import argparse
import hashlib
import platform
import sklearn
from datetime import datetime, timezone
try:
    from .synthetic import FEATURES, synthetic_data
except ImportError:
    from synthetic import FEATURES, synthetic_data

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=50000)
    parser.add_argument('--seed', type=int, default=42)
    args=parser.parse_args()
    if args.samples < 1000: parser.error('Use at least 1000 samples')
    df=synthetic_data(args.samples,args.seed)
    X=df[FEATURES];y=df.fraud
    X_train,X_temp,y_train,y_temp=train_test_split(X,y,test_size=.3,stratify=y,random_state=args.seed)
    X_val,X_test,y_val,y_test=train_test_split(X_temp,y_temp,test_size=.5,stratify=y_temp,random_state=args.seed)
    model=RandomForestClassifier(n_estimators=110,max_depth=12,min_samples_leaf=5,class_weight='balanced_subsample',random_state=args.seed,n_jobs=-1)
    model.fit(X_train,y_train)
    val_p=model.predict_proba(X_val)[:,1]
    thresholds=np.linspace(.15,.85,29)
    threshold=float(max(thresholds,key=lambda t:f1_score(y_val,val_p>=t,zero_division=0)))
    test_p=model.predict_proba(X_test)[:,1];test_pred=test_p>=threshold
    metrics={'accuracy':round(float(accuracy_score(y_test,test_pred)),4),'roc_auc':round(float(roc_auc_score(y_test,test_p)),4),'precision':round(float(precision_score(y_test,test_pred,zero_division=0)),3),'recall':round(float(recall_score(y_test,test_pred,zero_division=0)),3),'f1':round(float(f1_score(y_test,test_pred,zero_division=0)),3),'pr_auc':round(float(average_precision_score(y_test,test_p)),3),'confusion_matrix':confusion_matrix(y_test,test_pred).tolist(),'test_samples':len(y_test)}
    dest=ROOT/'artifacts';dest.mkdir(exist_ok=True)
    joblib.dump(model,dest/'fraud_model.joblib')
    metadata={'version':'synthetic-demo-v2','threshold':round(threshold,4),'features':FEATURES,'metrics':metrics,'training_source':'synthetic generated data','warning':'DEMO ONLY. Not validated on real credit-card fraud.'}
    metadata.update(samples=args.samples, seed=args.seed,
        split_samples={'train':len(y_train),'validation':len(y_val),'test':len(y_test)},
        label_fraud_rate=float(y.mean()), trained_at=datetime.now(timezone.utc).isoformat(),
        sklearn_version=sklearn.__version__, python_version=platform.python_version(),
        model_sha256=hashlib.sha256((dest/'fraud_model.joblib').read_bytes()).hexdigest(),
        threshold_selection='Best validation F1; test set used only for final evaluation')
    (dest/'metadata.json').write_text(json.dumps(metadata,indent=2))
    print('Saved model and metadata:',metadata)

if __name__=='__main__':main()
