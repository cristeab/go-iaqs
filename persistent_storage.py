#!/usr/bin/env python3
#
# sudo systemctl status influxdb3-core
# journalctl -u influxdb3-core
# influxdb3 show databases
# curl "http://localhost:8181/health" --header "Authorization: Bearer $INFLUXDB3_ADMIN_TOKEN"

from influxdb_client_3 import InfluxDBClient3, WritePrecision, Point
from typing import Dict
from logger_configurator import LoggerConfigurator
from enum import Enum
import pandas
import os, sys


class PersistentStorage:
    auth_scheme = "Bearer"
    host = "http://localhost:8181"

    class Database(Enum):
        Dust = "dust"
        Gas = "gas"

    class Point(Enum):
        PM = "pmsa003_"
        SCD41 = "scd41"

    def __init__(self, host = "http://localhost:8181"):
        self.host = host
        self._logger = LoggerConfigurator.configure_logger(self.__class__.__name__)
        self._token = os.environ.get("INFLUXDB3_AUTH_TOKEN")
        if not self._token:
            print("Error: INFLUXDB3_AUTH_TOKEN environment variable is not set.")
            sys.exit(1)

        self._clients: Dict[str, InfluxDBClient3] = {}
        self._verify_token()

    def get_client(self, database: str) -> InfluxDBClient3:
        """Get or create a client for specific database"""
        if database not in self._clients:
            self._clients[database] = InfluxDBClient3(
                host=self.host,
                token=self._token,
                database=database,
                auth_scheme=self.auth_scheme
            )
        return self._clients[database]

    def _verify_token(self):
        try:
            client = self.get_client(self.Database.Dust.value)
            client.query("SELECT 1")
            self._logger.info("Token verification successful.")
        except Exception as e:
            if "unauthorized" in str(e).lower() or "authentication" in str(e).lower():
                self._logger.error(f"Token verification failed: {e}")
            else:
                self._logger.error(f"An unexpected error occurred during token verification: {e}")
            sys.exit(1)

    def _read(self, db: Database, point_name):
        try:
            client = self.get_client(db.value)
            df = client.query(
                        query=f'SELECT * FROM "{point_name}" WHERE time > now() - interval \'10 minutes\' ORDER BY time DESC LIMIT 1',
                        language="sql",
                        mode="pandas"
                    )
            records = df.to_dict(orient="records")
            return records[-1] if records else None
        except Exception as e:
            self._logger.error(f"Cannot read from {point_name}: {e}")
        return None

    def read_pm(self, i: int):
        return self._read(self.Database.Dust, f'{self.Point.PM.value}{i}')

    def read_co2_data(self):
        return self._read(self.Database.Gas, self.Point.SCD41.value)
