FROM grafana/grafana:latest

ENV GF_SERVER_HTTP_PORT=8080
ENV GF_SERVER_HTTP_ADDR=0.0.0.0

COPY provisioning /etc/grafana/provisioning
COPY dashboards /var/lib/grafana/dashboards

EXPOSE 8080
