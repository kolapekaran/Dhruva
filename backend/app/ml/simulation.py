def simulate_future(model, temp, wind, hours):
    results = []
    for h in range(hours):
        is_night = 1 if (h < 6 or h > 20) else 0
        wind_chill = temp - (wind * 0.7)

        X = [[temp, h, wind, is_night, wind_chill, temp*wind]]
        pred = model.predict(X)[0]

        results.append(round(pred, 2))
    return results