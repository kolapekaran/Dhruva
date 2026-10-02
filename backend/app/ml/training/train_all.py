from app.ml.training.train_load import main as train_load
from app.ml.training.train_solar import main as train_solar
from app.ml.training.train_wind import main as train_wind
from app.ml.training.train_failure import main as train_failure
from app.ml.training.train_anomaly import main as train_anomaly
from app.ml.training.train_asset_health import train as train_asset_health

def main():
    train_load(); train_solar(); train_wind(); train_failure(); train_anomaly(); train_asset_health('battery'); train_asset_health('generator')

if __name__=='__main__': main()
