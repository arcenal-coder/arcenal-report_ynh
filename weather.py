"""Forecast snapshot for the report, using approximate browser coordinates."""
import json
import math
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo


def coordinates(location):
    if not isinstance(location, dict):
        raise ValueError('Localisation invalide.')
    lat, lon = location.get('latitude'), location.get('longitude')
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (lat, lon)):
        raise ValueError('Coordonnées invalides.')
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Coordonnées hors limites.')
    return round(lat, 2), round(lon, 2)


def summarize(data, lat, lon):
    daily = data['daily']
    def value(key):
        number = daily[key][0]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValueError('Prévision incomplète.')
        return number
    low, high = value('temperature_2m_min'), value('temperature_2m_max')
    wind, gust = value('wind_speed_10m_max'), value('wind_gusts_10m_max')
    rain, code = value('precipitation_sum'), value('weather_code')
    alerts = []
    if wind >= 50 or gust >= 60:
        alerts.append(f'Vent fort prévu : vent maximal {wind:g} km/h, rafales {gust:g} km/h. Vérifier les conditions de travail sur site.')
    if rain >= 1:
        alerts.append(f"{'Fortes précipitations prévues' if rain >= 10 else 'Précipitations prévues'} : {rain:g} mm sur la journée. Prévoir la protection des équipements et des accès.")
    if code in (95, 96, 99):
        alerts.append('Orage prévu dans la zone. Consulter la vigilance officielle et les consignes du site.')
    return {'date': daily['time'][0], 'latitude': lat, 'longitude': lon,
            'temperature_min': low, 'temperature_max': high, 'wind_max': wind,
            'gust_max': gust, 'precipitation': rain, 'alerts': alerts,
            'retrieved_at': datetime.now(ZoneInfo('Europe/Paris')).isoformat()}


def fetch_forecast(location):
    lat, lon = coordinates(location)
    query = urlencode({'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 1,
        'daily': 'temperature_2m_min,temperature_2m_max,wind_speed_10m_max,wind_gusts_10m_max,precipitation_sum,weather_code',
        'wind_speed_unit': 'kmh'})
    with urlopen('https://api.open-meteo.com/v1/forecast?' + query, timeout=10) as response:
        data = json.loads(response.read(1_000_000))
    return summarize(data, lat, lon)


def report_lines(snapshot):
    return ['MÉTÉO LOCALE',
        f"Prévisions du {snapshot['date']} pour la position du navigateur ({snapshot['latitude']:.2f}, {snapshot['longitude']:.2f}).",
        f"Température : {snapshot['temperature_min']:g} à {snapshot['temperature_max']:g} °C. Vent maximal : {snapshot['wind_max']:g} km/h. Rafales : {snapshot['gust_max']:g} km/h. Précipitations : {snapshot['precipitation']:g} mm.",
        *[f'• Message météo : {alert}' for alert in snapshot['alerts']],
        *([] if snapshot['alerts'] else ['Aucun seuil de signalement atteint dans ces prévisions ; cela ne garantit pas l’absence de risque.']),
        'Seuils indicatifs du POC : vent ≥ 50 km/h ou rafales ≥ 60 km/h ; précipitations ≥ 1 mm/jour (fortes ≥ 10 mm/jour) ; code météo orage.',
        f"Source : Open-Meteo · https://open-meteo.com/ · Consultation : {snapshot['retrieved_at']}",
        'Messages issus des prévisions, distincts des alertes officielles de Météo-France.']
