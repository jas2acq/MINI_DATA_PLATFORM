#!/bin/bash
set -e

mkdir -p certs/minio certs/postgres certs/postgres-airflow certs/kes certs/airflow

generate_openssl_config() {
cat <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = GH
ST = Accra
L = Accra
O = MiniDataPlatform
CN = "$1"

[v3_req]
$(if [ -n "$2" ]; then echo "subjectAltName = $2"; fi)
EOF
}

echo "🔐 Generating Certificate Authority..."
openssl genrsa -out certs/ca.key 4096
openssl req -x509 -new -nodes -key certs/ca.key -sha256 -days 3650 -out certs/ca.crt \
    -subj "//C=GH\\ST=Accra\\L=Accra\\O=MiniDataPlatform\\CN=minidata.ca"

echo "🔐 Generating MinIO Server Certificate..."
openssl genrsa -out certs/minio/private.key 2048
generate_openssl_config "minio" "DNS:minio,IP:127.0.0.1" > certs/minio/openssl.cnf
openssl req -new -key certs/minio/private.key -out certs/minio/server.csr -config certs/minio/openssl.cnf
openssl x509 -req -in certs/minio/server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out certs/minio/public.crt -days 365 -sha256 -extensions v3_req -extfile certs/minio/openssl.cnf

echo "🔐 Generating PostgreSQL Analytics Server Certificate..."
openssl genrsa -out certs/postgres/server.key 2048
chmod 0600 certs/postgres/server.key
generate_openssl_config "postgres-analytics" "DNS:postgres-analytics,IP:127.0.0.1" > certs/postgres/openssl.cnf
openssl req -new -key certs/postgres/server.key -out certs/postgres/server.csr -config certs/postgres/openssl.cnf
openssl x509 -req -in certs/postgres/server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out certs/postgres/server.crt -days 365 -sha256 -extensions v3_req -extfile certs/postgres/openssl.cnf

echo "🔐 Generating PostgreSQL Airflow Server Certificate..."
openssl genrsa -out certs/postgres-airflow/server.key 2048
chmod 0600 certs/postgres-airflow/server.key
generate_openssl_config "postgres-airflow" "DNS:postgres-airflow,IP:127.0.0.1" > certs/postgres-airflow/openssl.cnf
openssl req -new -key certs/postgres-airflow/server.key -out certs/postgres-airflow/server.csr -config certs/postgres-airflow/openssl.cnf
openssl x509 -req -in certs/postgres-airflow/server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out certs/postgres-airflow/server.crt -days 365 -sha256 -extensions v3_req -extfile certs/postgres-airflow/openssl.cnf

echo "🔐 Generating KES Server Certificate..."
openssl genrsa -out certs/kes/kes-server.key 2048
generate_openssl_config "kes" "DNS:kes,IP:127.0.0.1" > certs/kes/openssl.cnf
openssl req -new -key certs/kes/kes-server.key -out certs/kes/kes-server.csr -config certs/kes/openssl.cnf
openssl x509 -req -in certs/kes/kes-server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out certs/kes/kes-server.cert -days 365 -sha256 -extensions v3_req -extfile certs/kes/openssl.cnf

echo "🔐 Generating MinIO Client Certificate..."
openssl genrsa -out certs/minio/client.key 2048
generate_openssl_config "minio-client-user" "" > certs/minio/client_openssl.cnf
openssl req -new -key certs/minio/client.key -out certs/minio/client.csr -config certs/minio/client_openssl.cnf
openssl x509 -req -in certs/minio/client.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out certs/minio/client.crt -days 365 -sha256 -extensions v3_req -extfile certs/minio/client_openssl.cnf

echo "🔐 Generating Airflow Webserver Certificate..."
openssl genrsa -out certs/airflow/server.key 2048
generate_openssl_config "airflow-webserver" "DNS:airflow-webserver,IP:127.0.0.1" > certs/airflow/openssl.cnf
openssl req -new -key certs/airflow/server.key -out certs/airflow/server.csr -config certs/airflow/openssl.cnf
openssl x509 -req -in certs/airflow/server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out certs/airflow/server.crt -days 365 -sha256 -extensions v3_req -extfile certs/airflow/openssl.cnf

echo "✅ All certificates generated successfully."
