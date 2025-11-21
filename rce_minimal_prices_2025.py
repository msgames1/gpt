diff --git a/rce_minimal_prices_2025.py b/rce_minimal_prices_2025.py
new file mode 100644
index 0000000000000000000000000000000000000000..ae573736488b45b9862c490900b7eba8cf8643c3
--- /dev/null
+++ b/rce_minimal_prices_2025.py
@@ -0,0 +1,129 @@
+"""
+Skrypt pobiera 15-minutowe dane RCE (PLN/MWh) z API PSE dla roku 2025,
+wylicza średnie ceny godzinowe oraz minimalne ceny godzinowe dla każdego dnia
+z uwzględnieniem najwcześniejszej godziny wystąpienia minimum.
+"""
+
+import sys
+from typing import List, Dict, Any
+
+import pandas as pd
+import requests
+from requests import RequestException
+
+# Stałe konfiguracyjne
+API_URL = "https://api.raporty.pse.pl/api/rce-pln"
+START_DATE = "2025-01-01"
+END_DATE = "2025-12-31"
+OUTPUT_CSV = "minimalne_ceny_godzinowe_2025.csv"
+
+
+def fetch_rce_data() -> List[Dict[str, Any]]:
+    """Pobiera dane RCE z API PSE dla zadanego zakresu dat.
+
+    Zwraca listę słowników z danymi 15-minutowymi.
+    Obsługuje paginację w przypadku zwróconego odnośnika "@odata.nextLink".
+    """
+
+    params = {
+        "$format": "json",
+        "$filter": f"doba ge {START_DATE} and doba le {END_DATE}",
+        "$orderby": "udtczas",
+    }
+
+    all_records: List[Dict[str, Any]] = []
+    next_url = API_URL
+
+    while next_url:
+        try:
+            response = requests.get(next_url, params=params if next_url == API_URL else None, timeout=30)
+            response.raise_for_status()
+        except RequestException as exc:  # obejmuje błędy HTTP i sieciowe
+            raise SystemExit(f"Błąd podczas pobierania danych: {exc}") from exc
+
+        try:
+            payload = response.json()
+        except ValueError as exc:
+            raise SystemExit(f"Nieprawidłowy format JSON w odpowiedzi API: {exc}") from exc
+
+        records = payload.get("value")
+        if records is None:
+            raise SystemExit("Brak danych w odpowiedzi API (pole 'value').")
+
+        all_records.extend(records)
+        next_url = payload.get("@odata.nextLink")
+
+    if not all_records:
+        raise SystemExit("Nie zwrócono żadnych danych z API.")
+
+    return all_records
+
+
+def compute_daily_minimums(data: List[Dict[str, Any]]) -> pd.DataFrame:
+    """Oblicza minimalne ceny godzinowe dla każdego dnia.
+
+    Przyjmuje listę rekordów 15-minutowych z polami "udtczas" oraz "rce_pln".
+    Zwraca DataFrame z kolumnami: data, godzina_min, cena_min_godzinna_PLN_MWh.
+    """
+
+    df = pd.DataFrame(data)
+
+    if "udtczas" not in df or "rce_pln" not in df:
+        raise SystemExit("W danych brakuje wymaganych pól 'udtczas' lub 'rce_pln'.")
+
+    # Konwersje typów
+    df["udtczas"] = pd.to_datetime(df["udtczas"], errors="coerce")
+    df["rce_pln"] = pd.to_numeric(df["rce_pln"], errors="coerce")
+    df = df.dropna(subset=["udtczas", "rce_pln"])
+
+    if df.empty:
+        raise SystemExit("Brak poprawnych danych po wstępnej obróbce.")
+
+    # Wyznaczenie pełnej godziny i uśrednianie 15-minutowych cen
+    df["godzina"] = df["udtczas"].dt.floor("H")
+    hourly = (
+        df.groupby("godzina", as_index=False)["rce_pln"].mean()
+        .rename(columns={"rce_pln": "cena_godzinna"})
+    )
+
+    hourly["data"] = hourly["godzina"].dt.date
+
+    # Wybranie minimalnej ceny godzinowej dla każdego dnia z najwcześniejszą godziną
+    daily_min = (
+        hourly.sort_values(by=["data", "cena_godzinna", "godzina"])
+        .groupby("data", as_index=False)
+        .first()
+    )
+
+    result = daily_min[["data", "godzina", "cena_godzinna"]].rename(
+        columns={
+            "godzina": "godzina_min",
+            "cena_godzinna": "cena_min_godzinna_PLN_MWh",
+        }
+    )
+
+    # Formatowanie kolumn daty i godziny do stringów
+    result["data"] = result["data"].astype(str)
+    result["godzina_min"] = result["godzina_min"].dt.strftime("%Y-%m-%d %H:%M")
+
+    return result
+
+
+def main() -> None:
+    # Pobierz dane z API
+    records = fetch_rce_data()
+
+    # Oblicz minimalne ceny godzinowe dla każdego dnia
+    minimal_prices = compute_daily_minimums(records)
+
+    # Zapis do pliku CSV z kodowaniem UTF-8
+    minimal_prices.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
+    print(f"Zapisano {len(minimal_prices)} wierszy do pliku: {OUTPUT_CSV}")
+
+
+if __name__ == "__main__":
+    try:
+        main()
+    except Exception as exc:  # przechwycenie niespodziewanych błędów na poziomie głównym
+        print(exc, file=sys.stderr)
+        sys.exit(1)
