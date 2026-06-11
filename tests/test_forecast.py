import unittest
from unittest.mock import patch

import rain


class ForecastBatchTests(unittest.TestCase):
    def test_load_forecast_uses_one_batch_request_and_maps_each_port(self):
        test_ports = {
            "Port A": {"lat": 1.0, "lon": 101.0, "region_group": "Region A"},
            "Port B": {"lat": 2.0, "lon": 102.0, "region_group": "Region B"},
        }
        api_response = [
            {"daily": {"time": ["2026-06-11"], "precipitation_sum": [1.5]}},
            {"daily": {"time": ["2026-06-11"], "precipitation_sum": [2.5]}},
        ]

        rain.load_forecast_data_today_cached.clear()
        with (
            patch.object(rain, "PORTS", test_ports),
            patch.object(rain, "request_json", return_value=api_response) as request_json,
        ):
            result = rain.load_forecast_data_today_cached("2026-06-11", forecast_days=7)

        self.assertEqual(request_json.call_count, 1)
        _, params = request_json.call_args.args
        self.assertEqual(params["latitude"], "1.0,2.0")
        self.assertEqual(params["longitude"], "101.0,102.0")
        self.assertEqual(set(result["port_name"]), {"Port A", "Port B"})
        self.assertEqual(result.attrs["failed_ports"], [])


if __name__ == "__main__":
    unittest.main()
