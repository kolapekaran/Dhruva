def ensemble_predict(models, X):
    preds = [m.predict(X)[0] for m in models]
    return sum(preds) / len(preds)