# retrain
import json
import joblib
from lightgbm import LGBMClassifier
from sklearn.utils.class_weight import compute_sample_weight
import pandas as pd

df = pd.read_csv('data/processed/modelB_dataset.csv')

# define model
X = df.loc[:, ['regime_diff','event_count_lag1', 'goldstein_std_lag1', 'goldstein_min_lag1', 'num_mentions_sum_lag1',
               'num_articles_sum_lag1', 'num_sources_sum_lag1', 'high_conflict_count_lag1', 'low_conflict_count_lag1',
               'quad4_count_lag1', 'high_conflict_pct_lag1', 'low_conflict_pct_lag1', 'quad4_pct_lag1']]
y = df['monthly_label']


with open('../outputs/para/lgb_01.json', 'r') as f:
    best_params = json.load(f)

weight_power = 0.3013525939572423

final_weights = compute_sample_weight('balanced', y) ** weight_power
 
final_model = LGBMClassifier(**best_params)
final_model.fit(X, y, sample_weight=final_weights)

 
joblib.dump(final_model, 'outputs/models/mod_lgb.pkl')

    