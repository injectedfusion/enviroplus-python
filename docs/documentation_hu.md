
# Dokumentáció

## Bevezetés

Ez a projekt az Enviro plus szenzorok adatait gyűjti és jeleníti meg. Az eszköz könnyen indítható asztali alkalmazásként vagy cronjob-ként.

## Telepítés

1. Telepítsd a szükséges függőségeket:
    ```bash
    pip install -r requirements.txt
    ```

2. Hozd létre az executables futtatásához:
    ```bash
    ./build_executable.sh
    ```

3. Futtasd az alkalmazást az asztali ikonnal vagy állíts be egy cronjob-t.

## Példák

A következő példák elérhetők:
- `sensorcommunity_combined_hu.py` - Sensor.Community integráció magyar nyelven
- `combined_hu.py` - Összes szenzor adat megjelenítése
- `all-in-one-no-pm_hu.py` - PM érzékelők nélküli adatmegjelenítés
- `all-in-one-enviro-mini_hu.py` - Kiválasztott Enviro plus szenzorok adatainak megjelenítése

## Használat

Az alkalmazás futtatásához használd az alábbi parancsot:
```bash
python3 examples/sensorcommunity_combined_hu.py
```

# További információ

További segítségért látogass el a [Sensor.Community](https://devices.sensor.community/) oldalra.