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
from sklearn.metrics import precision_score,recall_score,f1_score,average_precision_score,confusion_matrix
from sklearn.model_selection import train_test_split

ROOT=Path(__file__).resolve().parent
FEATURES=['distance_from_home','distance_from_last_transaction','ratio_to_median_purchase_price','repeat_retailer','used_chip','used_pin_number','online_order']

def synthetic_data(n=12000,seed=42):
    rng=np.random.default_rng(seed)
    df=pd.DataFrame({
      'distance_from_home':rng.exponential(45,n),
      'distance_from_last_transaction':rng.exponential(28,n),
      'ratio_to_median_purchase_price':rng.lognormal(0,0.85,n),
      'repeat_retailer':rng.binomial(1,.72,n),
      'used_chip':rng.binomial(1,.68,n),
      'used_pin_number':rng.binomial(1,.44,n),
      'online_order':rng.binomial(1,.38,n)})
    score=-4.4+0.014*df.distance_from_home+0.013*df.distance_from_last_transaction+0.37*df.ratio_to_median_purchase_price+0.8*(1-df.repeat_retailer)+0.75*(1-df.used_chip)+0.3*df.online_order-0.5*df.used_pin_number
    p=1/(1+np.exp(-np.clip(score,-20,20)))
    df['fraud']=rng.binomial(1,p)
    return df

def main():
    df=synthetic_data()
    X=df[FEATURES];y=df.fraud
    X_train,X_temp,y_train,y_temp=train_test_split(X,y,test_size=.3,stratify=y,random_state=42)
    X_val,X_test,y_val,y_test=train_test_split(X_temp,y_temp,test_size=.5,stratify=y_temp,random_state=42)
    model=RandomForestClassifier(n_estimators=110,max_depth=12,min_samples_leaf=5,class_weight='balanced_subsample',random_state=42,n_jobs=-1)
    model.fit(X_train,y_train)
    val_p=model.predict_proba(X_val)[:,1]
    thresholds=np.linspace(.15,.85,29)
    threshold=float(max(thresholds,key=lambda t:f1_score(y_val,val_p>=t,zero_division=0)))
    test_p=model.predict_proba(X_test)[:,1];test_pred=test_p>=threshold
    metrics={'precision':round(float(precision_score(y_test,test_pred,zero_division=0)),3),'recall':round(float(recall_score(y_test,test_pred,zero_division=0)),3),'f1':round(float(f1_score(y_test,test_pred,zero_division=0)),3),'pr_auc':round(float(average_precision_score(y_test,test_p)),3),'confusion_matrix':confusion_matrix(y_test,test_pred).tolist(),'test_samples':len(y_test)}
    dest=ROOT/'artifacts';dest.mkdir(exist_ok=True)
    joblib.dump(model,dest/'fraud_model.joblib')
    metadata={'version':'synthetic-demo-v1','threshold':round(threshold,4),'features':FEATURES,'metrics':metrics,'training_source':'synthetic generated data','warning':'DEMO ONLY. Not validated on real credit-card fraud.'}
    (dest/'metadata.json').write_text(json.dumps(metadata,indent=2))
    print('Saved model and metadata:',metadata)

if __name__=='__main__':main()
