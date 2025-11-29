#!/usr/bin/env python3

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
from persistent_storage import PersistentStorage
from fastapi.websockets import WebSocketDisconnect
from constants import SLEEP_DURATION_SECONDS, normalize_and_format_pandas_timestamp
from logger_configurator import LoggerConfigurator


app = FastAPI()

# Serve static files (HTML, JS, CSS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# InfluxDB connection
storage = PersistentStorage("http://192.168.77.44:8181")

# Logger
logger = LoggerConfigurator.configure_logger("GO-IAQS")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r") as file:
        return file.read()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Query latest data from InfluxDB
            for i in range(2):
                pm_data = storage.read_pm(i)
                if pm_data is not None:
                    try:
                        payload = {
                            "pm10_" + str(i): pm_data["pm10_cf1"],
                            "pm25_" + str(i): pm_data["pm25_cf1"],
                            "pm100_" + str(i): pm_data["pm100_cf1"],
                            "pm03plus_" + str(i): pm_data["gr03um"],
                            "pm05plus_" + str(i): pm_data["gr05um"],
                            "pm10plus_" + str(i): pm_data["gr10um"],
                            "pm25plus_" + str(i): pm_data["gr25um"],
                            "pm50plus_" + str(i): pm_data["gr50um"],
                            "pm100plus_" + str(i): pm_data["gr100um"]
                        }
                    except KeyError as e:
                        logger.error(f"KeyError processing PM{i} data: {e}")
            # CO2
            co2_data = storage.read_co2_data()
            if co2_data is not None:
                try:
                    ts = normalize_and_format_pandas_timestamp(co2_data["time"])
                    payload = payload | {
                        "co2": co2_data["co2"]
                    }
                except Exception as e:
                    logger.error(f"Error processing CO2 data: {e}")
            # Send data to client
            data = {
                "type": "data",
                "payload": payload
            }
            await websocket.send_json(data)
            # Wait before sending next update
            await asyncio.sleep(SLEEP_DURATION_SECONDS)
    except WebSocketDisconnect:
        print("Client disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888, ssl_keyfile="key.pem", ssl_certfile="cert.pem")
