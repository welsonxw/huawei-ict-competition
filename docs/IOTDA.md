# Field sensors over MQTT and Huawei Cloud IoTDA (Phase 10)

Every path ends in the same validation and storage code as `POST /api/iot/readings`, so readings look identical
in the Farm monitor whichever way they arrive. The device list shows the path ("via HTTP / MQTT / Huawei IoTDA").
Simulated devices keep the **"Simulated device"** label on every path.

```
ESP32 / simulator ──MQTT──► Huawei Cloud IoTDA ──HTTP data forwarding──► POST /api/iot/iotda/push/<token>  ┐
ESP32 / simulator ──MQTT──► local Mosquitto ──► flask mqtt-bridge ─────────────────────────────────────────┼─► ingest() ─► sensor_readings
ESP32 / simulator ──HTTP (X-Device-Id / X-Device-Key)──► POST /api/iot/readings ──────────────────────────┘
```

Devices publish the IoTDA device-side topic and payload on both MQTT paths, so firmware does not change between
local and cloud:

```
topic   $oc/devices/{device_id}/sys/properties/report
payload {"services":[{"service_id":"Sensor",
                      "properties":{"soil_moisture_pct":31.5,"air_temp_c":29.1,"air_rh_pct":82,"leaf_wet":0},
                      "event_time":"20260101T080000Z"}]}
```

`event_time` is UTC `yyyyMMddTHHmmssZ` (optional; server time is used when missing). Property names and valid ranges
are the ones in `config/iot.yaml`. Out-of-range values, future times and unknown devices are rejected and nothing
from that message is stored.

## Local development (Mosquitto)

```bash
docker compose --profile iot up -d --build          # adds mosquitto (127.0.0.1:1883) and mqtt-bridge
docker compose exec backend flask add-device 1 --simulated   # prints e.g. tg-1-abcd1234 + a key
python scripts/device_simulator.py --mqtt mqtt://localhost:1883 --device tg-1-abcd1234 \
    --lat 1.8548 --lon 103.3345 --interval 5 --speed 720 --count 10
docker compose logs -f mqtt-bridge                  # "mqtt tg-1-abcd1234: stored 1 reading(s)"
```

The local broker allows anonymous clients and is bound to localhost / the compose network. It is for development only;
in the cloud IoTDA authenticates every device with its own secret.

## Huawei Cloud IoTDA

Console steps follow Huawei's IoTDA user guide (links below). Nothing here has been run against a real IoTDA
instance from this repository yet.

1. **Instance.** Open IoTDA in the same region as the ECS (e.g. AP-Singapore) and note the MQTTS device access
   address (port 8883) on the instance's *Access Details* page.
2. **Product.** *Products > Create Product*: protocol MQTT, data format JSON. Under *Model Definition* import
   `deploy/iotda/taniguard_sensor_model.json` (one service `Sensor` with the same property names as the API).
   Copy the **product ID** into `IOTDA_PRODUCT_ID` in `.env`.
3. **Devices.** For each sensor, first register it in TaniGuard so it belongs to a plot:
   `flask add-device <plot_id> [--simulated]` → device id `tg-…` and key. Then in IoTDA *Devices > Register Device*
   use **node ID = the TaniGuard device id** and **secret = the TaniGuard device key**. IoTDA's device ID becomes
   `<product_id>_<node_id>`; TaniGuard maps it back to the plot.
4. **Forwarding rule.** Generate a token (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) and set
   `IOTDA_PUSH_TOKEN` in `.env`. In *Rules > Data Forwarding* create a rule with data source **Device property**,
   trigger **Device property reported**, and target **Third-party application (HTTP push)** with URL
   `https://<your domain>/api/iot/iotda/push/<IOTDA_PUSH_TOKEN>`. IoTDA only pushes to HTTPS with a CA certificate
   uploaded to IoTDA (see the HTTP/HTTPS forwarding guide), so finish the HTTPS step of `DEPLOY_HUAWEI_CLOUD.md` first.
   Keep the URL secret: the token is what authenticates IoTDA to the API.
5. Restart the backend. *Behind the scenes* now shows IoTDA as in use.
6. **Test with the simulator** (no hardware needed; stays labelled "Simulated device" if registered with `--simulated`):

   ```bash
   python scripts/device_simulator.py --mqtt mqtts://<iotda-mqtts-host>:8883 --iotda-product <product_id> \
       --device tg-1-abcd1234 --key <device key> --lat 1.8548 --lon 103.3345 --interval 60
   ```

   The simulator connects like a real device: ClientId `<device_id>_0_0_<YYYYMMDDHH>`, username = device ID,
   password = HMAC-SHA256 of the secret keyed with that UTC timestamp.

The push endpoint always answers 200 (with `accepted: 0` and an error for bad messages or unknown devices) so that
IoTDA does not blocklist the URL; a wrong token gets 404.

## Real hardware

An ESP32 with a capacitive soil-moisture probe and a DHT22/SHT31 can use Huawei's IoT Device SDK or any MQTT client
with the credentials above and publish the payload shown at the top. No TaniGuard code changes are needed.

## References

- IoTDA device MQTT connection authentication: https://support.huaweicloud.com/intl/en-us/api-iothub/iot_06_v5_3009.html
- Device property reporting (topic and payload): https://support.huaweicloud.com/intl/en-us/api-iothub/iot_06_v5_3010.html
- Push a device property reporting notification (forwarded format): https://support.huaweicloud.com/intl/en-us/api-iothub/iot_06_v5_01202.html
- HTTP/HTTPS data forwarding: https://support.huaweicloud.com/intl/en-us/usermanual-iothub/iot_01_0001.html
