Situation
When I configure the Proxmox push metrics to my influxdb server, I got this error

```log_influxdb
2025-08-25T03:00:47.732822Z ERROR influxdb3_server::http: Error while handling request error=write buffer error: parsing for line protocol failed method=POST path="/api/v2/write" content_length=Some("436") client_ip=192.168.1.120
```
Which probaly mean there errors related to parsing
Task:
Investigate this issues to find the root cause
Action:
probably because uncompleted data result in this issues, so I found the confiugration default related to these

# Proxmox influx db push default:
https://registry.terraform.io/providers/bpg/proxmox/0.82.1/docs/resources/virtual_environment_metrics_server

influx_max_body_size (Number) InfluxDB max-body-size in bytes. Requests are batched up to this size. If not set, PVE default is 25000000.

On the other hand, the default in influxdb is

```bash
influxdb3 serve --help-all
```
Network Options:
  --max-http-request-size <SIZE>   Maximum size of HTTP requests [default: 10485760]
                                  [env: INFLUXDB3_MAX_HTTP_REQUEST_SIZE=]

In conclusion, the mismatch cause the problem

So I have change in Metrics server decrease to 10485760 to match the influxdb

