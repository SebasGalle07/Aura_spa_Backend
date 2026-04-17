FROM grafana/grafana:latest

ENV GF_SERVER_HTTP_PORT=8080
ENV GF_SERVER_HTTP_ADDR=0.0.0.0
ENV GF_SECURITY_ADMIN_USER=admin
ENV GF_SECURITY_ADMIN_PASSWORD=AuraSpa2026!
ENV GF_USERS_ALLOW_SIGN_UP=false

COPY provisioning /etc/grafana/provisioning
COPY dashboards /var/lib/grafana/dashboards

EXPOSE 8080
