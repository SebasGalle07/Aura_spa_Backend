FROM prom/prometheus:latest

COPY prometheus.cloud.yml /etc/prometheus/prometheus.yml

EXPOSE 8080

ENTRYPOINT ["/bin/prometheus"]
CMD ["--config.file=/etc/prometheus/prometheus.yml", "--web.enable-lifecycle", "--web.listen-address=:8080"]
