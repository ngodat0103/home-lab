#!/bin/bash
helm repo add ot-helm https://ot-container-kit.github.io/helm-charts/
helm upgrade redis-operator ot-helm/redis-operator \
  --install --create-namespace --namespace redis --create-namespace
