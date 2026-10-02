import numpy as np

def confidence_score(model, X):
    preds = [model.predict(X)[0] for _ in range(5)]
    return round(100 - np.std(preds), 2)