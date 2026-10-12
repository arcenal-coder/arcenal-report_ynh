import unittest
from unittest.mock import patch
import weather
import app
import test_api


class WeatherTest(unittest.TestCase):
    def forecast(self, wind=20, gust=30, rain=0, code=0):
        return {'daily': {'time':['2026-10-12'], 'temperature_2m_min':[10],
            'temperature_2m_max':[18], 'wind_speed_10m_max':[wind],
            'wind_gusts_10m_max':[gust], 'precipitation_sum':[rain], 'weather_code':[code]}}

    def test_wind_rain_and_thunderstorm_messages(self):
        snapshot = weather.summarize(self.forecast(50, 70, 12, 95), 48.85, 2.35)
        self.assertEqual(len(snapshot['alerts']), 3)
        self.assertIn('Orage prévu', ' '.join(snapshot['alerts']))

    def test_calm_weather_is_not_an_official_all_clear(self):
        snapshot = weather.summarize(self.forecast(), 48.85, 2.35)
        self.assertEqual(snapshot['alerts'], [])
        self.assertIn('ne garantit pas', ' '.join(weather.report_lines(snapshot)))

    def test_rejects_invalid_coordinates_and_missing_forecasts(self):
        for location in ({'latitude':True,'longitude':0}, {'latitude':91,'longitude':0}, {'latitude':float('nan'),'longitude':0}):
            with self.assertRaises(ValueError):
                weather.coordinates(location)
        data = self.forecast(); data['daily']['precipitation_sum'] = [None]
        with self.assertRaises(ValueError):
            weather.summarize(data, 0, 0)


class WeatherApiTest(test_api.ApiTest):
    def test_report_contains_weather_and_keeps_it_when_saved(self):
        import json
        mission_uuid = app.database.list_missions(app.DATABASE_PATH)[0]['uuid']
        snapshot = weather.summarize(WeatherTest().forecast(50,70,12,95), 48.85,2.35)
        with patch('weather.fetch_forecast', return_value=snapshot):
            status, report = self.request('POST', f'/api/v1/missions/{mission_uuid}/report',
                json.dumps({'author':'Jean Dupont','location':{'latitude':48.85,'longitude':2.35}}).encode())
        self.assertEqual(status, '201 Created')
        self.assertIn('MÉTÉO LOCALE', report['content'])
        self.assertIn('Orage prévu', report['content'])
        self.assertIn('2026-10-12', report['content'])

    def test_weather_failure_does_not_block_report(self):
        import json
        mission_uuid = app.database.list_missions(app.DATABASE_PATH)[0]['uuid']
        with patch('weather.fetch_forecast', side_effect=OSError('Unavailable')):
            status, report = self.request('POST', f'/api/v1/missions/{mission_uuid}/report',
                json.dumps({'author':'Jean Dupont','location':{'latitude':48.85,'longitude':2.35}}).encode())
        self.assertEqual(status, '201 Created')
        self.assertIn('Prévisions indisponibles', report['content'])
