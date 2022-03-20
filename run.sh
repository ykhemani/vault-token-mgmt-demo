#!/bin/bash

VAULT_TOKEN=$(vault token create -format=json -role python-hvac-demo -ttl 1m | jq -r .auth.client_token) \
  ./vault-token-mgmt-demo.py
