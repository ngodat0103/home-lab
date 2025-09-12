#!/bin/bash
# https://argo-cd.readthedocs.io/en/stable/getting_started/

helm upgrade --install argocd-prod . -n argocd --create-namespace
