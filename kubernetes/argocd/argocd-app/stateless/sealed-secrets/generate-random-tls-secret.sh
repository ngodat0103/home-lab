#!/bin/bash
# Just for quick testing

openssl genrsa -out sealed-secrets.key 4096
openssl req -new -x509 -key sealed-secrets.key -out sealed-secrets.crt -days 36500 -subj "/CN=sealed-secret-controller"
# Create the TLS secret
kubectl create secret tls sealed-secrets-key \
  --cert=sealed-secrets.crt \
  --key=sealed-secrets.key \
  -n sealed-secrets