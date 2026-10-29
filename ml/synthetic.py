"""Fictional population only. Labels are stochastic, never model predictions."""
import numpy as np
import pandas as pd
FEATURES = ['distance_from_home', 'distance_from_last_transaction',
            'ratio_to_median_purchase_price', 'repeat_retailer', 'used_chip',
            'used_pin_number', 'online_order']

def synthetic_data(n=50000, seed=42):
    rng = np.random.default_rng(seed)
    online = rng.binomial(1, .38, n)
    chip = rng.binomial(1, .85, n) * (1 - online)
    pin = rng.binomial(1, .65, n) * chip
    df = pd.DataFrame({
        'distance_from_home': rng.exponential(45, n),
        'distance_from_last_transaction': rng.exponential(28, n),
        'ratio_to_median_purchase_price': rng.lognormal(0, .85, n),
        'repeat_retailer': rng.binomial(1, .72, n),
        'used_chip': chip, 'used_pin_number': pin, 'online_order': online})
    score = (-4.4 + .014 * df.distance_from_home
             + .013 * df.distance_from_last_transaction
             + .37 * df.ratio_to_median_purchase_price
             + .8 * (1 - df.repeat_retailer) + .75 * (1 - df.used_chip)
             + .3 * df.online_order - .5 * df.used_pin_number)
    probability = 1 / (1 + np.exp(-np.clip(score, -20, 20)))
    df['fraud'] = rng.binomial(1, probability)
    return df
