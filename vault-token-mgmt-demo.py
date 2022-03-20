#!/usr/bin/env python3

########################################################################
# Example python script that uses the hvac library to authenticate with 
# HashiCorp Vault.
# 
# Creates thread with timer to renew token when the token reaches half
# of the creation TTL.
#
# Creates thread to periodically log the remaining token TTL.
# Disable by setting environment variable TOKEN_WATCH_ENABLED=False.
# Adjust interval after which token is checked by setting
# TOKEN_WATCH_INTERVAL=<int> (default: 5). Unit: seconds.
#
# Creates thread with timer to renew lease for dynamic database secrets
# when lease for secret reaches half of the creation TTL.
#
# Creates thread to periodically log the remaining TTL on the dynamic
# database lease.
# Disable by setting environment variable LEASE_WATCH_ENABLED=False.
# Adjust interval after which lease is checked by setting
# LEASE_WATCH_INTERVAL=<int> (default: 5). Unit: seconds.
#

import logging
from operator import le
import hvac
from os import environ, _exit, path
import sys
from time import sleep
from signal import signal, SIGINT
from threading import Thread, Timer, current_thread
from flask import Flask, render_template, request, redirect

def renew_token():
  logging.info("Renewing token")
  client.auth.token.renew_self()
  token = client.auth.token.lookup_self()
  ttl = token['data']['ttl']
  logging.info("Token TTL after renewal: %s", ttl)
  Timer(ttl/2,renew_token).start()

def token_watch():
  logging.debug("token_watch starting")
  token = client.auth.token.lookup_self()
  ttl = token['data']['ttl']
  logging.info("token_watch: Token TTL: %s", ttl)
  t_token_watch = Timer(token_watch_interval, token_watch)
  t_token_watch.daemon = True
  t_token_watch.start()
  logging.debug("token_watch finishing")

def renew_lease(lease_id):
  logging.info("Renewing lease %s", lease_id)
  renew = client.sys.renew_lease(lease_id=lease_id)
  ttl = renew["lease_duration"]
  logging.info("Renewed lease %s. New TTL: %s", lease_id, ttl)
  Timer(ttl/2, renew_lease,[lease_id]).start()

def lease_watch(lease_id):
  logging.debug("lease_watch starting")
  lease = client.sys.read_lease(lease_id=lease_id)
  #print(lease)
  logging.info("lease_watch: %s. TTL: %s", lease_id, lease["data"]["ttl"])
  t_lease_watch = Timer(lease_watch_interval, lease_watch, [lease_id])
  t_lease_watch.daemon = True
  t_lease_watch.start()
  logging.debug("lease_watch finishing")

def sigint_handler(sig, frame):
  logging.info("CTRL-C pressed. Exiting.")
  sys.exit(0)

if __name__ == '__main__':
  # logging
  format = "%(asctime)s: %(message)s"
  date_format = "%Y-%m-%d %H:%M:%S %Z"
  logging.basicConfig(format=format, level=logging.INFO, datefmt=date_format)
  logging.info("Starting %s", path.basename(__file__))

  # handle sigint (ctrl-c)
  signal(SIGINT, sigint_handler)

  # config
  try:
    vault_addr = environ['VAULT_ADDR']
  except KeyError:
    logging.error('[error]: `VAULT_ADDR` environment variable not set.')
    sys.exit(1)

  try:
    vault_token = environ['VAULT_TOKEN']
  except KeyError:
    logging.error('[error]: `VAULT_TOKEN` environment variable not set.')
    sys.exit(1)

  token_watch_interval = environ.get('TOKEN_WATCH_INTERVAL', 5)
  token_watch_enabled = environ.get('TOKEN_WATCH_ENABLED', 'true')
  token_watch_enabled = token_watch_enabled.lower() in ('true','t','yes','y')
  logging.info("token_watch_enabled: %s", token_watch_enabled)

  lease_watch_interval = environ.get('LEASE_WATCH_INTERVAL', 5)
  lease_watch_enabled = environ.get('LEASE_WATCH_ENABLED', 'true')
  lease_watch_enabled = lease_watch_enabled.lower() in ('true','t','yes','y')

  # Vault Client
  client = hvac.Client(
    url = vault_addr,
    token = vault_token
  )

  # Vault token
  token = client.auth.token.lookup_self()
  # ttl when token was created
  creation_ttl = token['data']['creation_ttl']
  logging.info("Token TTL at creation: %s", creation_ttl)
  # current ttl
  ttl = token['data']['ttl']
  logging.info("Token TTL: %s", ttl)

  # renew now if we're already past half the creation ttl
  if ttl <= creation_ttl/2:
    renew_token
  else:
    # token renewal thread
    t_renew_token = Timer(ttl/2, renew_token)
    t_renew_token.daemon = True
    t_renew_token.start()

  # watch token every token_watch_interval
  # for demonstration purposes
  if token_watch_enabled:
    logging.info("Starting token watch.")
    t_token_watch = Timer(token_watch_interval, token_watch)
    t_token_watch.daemon = True
    t_token_watch.start()

  postgres_credentials = client.secrets.database.generate_credentials(
    name = 'demo-role',
    mount_point = 'postgres',
  )
  postgres_lease_id = postgres_credentials['lease_id']
  postgres_ttl = postgres_credentials['lease_duration']
  postgres_username = postgres_credentials['data']['username']
  postgres_password = postgres_credentials['data']['password']
  logging.info("Postgres dynamic database credentials obtained.")
  logging.info("Postgres Lease ID:  %s", postgres_lease_id)
  logging.info("Postgres Lease TTL: %s", postgres_ttl)
  # postgres dynamic database credentials lease renewal thread
  t_renew_lease = Timer(postgres_ttl/2, renew_lease, [postgres_lease_id])
  t_renew_lease.daemon = True
  t_renew_lease.start()
  # watch lease every lease_watch_internval
  # for demonstration purposes
  if lease_watch_enabled:
    t_lease_watch = Timer(lease_watch_interval, lease_watch, [postgres_lease_id])
    t_lease_watch.daemon = True
    t_lease_watch.start()

  # http api / ui
  app = Flask(__name__)
  app.config['TEMPLATES_AUTO_RELOAD'] = True
  title = "Vault Token Management in Python"
  # landing page
  @app.route("/")
  def home():
    global title
    global token_watch_interval
    return render_template(
      'index.html', 
      title=title, 
      token_watch_interval=token_watch_interval,
      lease_watch_interval=lease_watch_interval,
    )

  # handle exit request
  @app.route("/v1/sys/exit", methods=["POST"])
  def api_exit():
    logging.info("api_exit called")
    _exit(0)

  # set token watch interval
  @app.route("/v1/sys/token_watch_interval", methods=["POST"])
  def set_token_watch_interval():
    global token_watch_interval
    if "token_watch_interval" in request.form:
      token_watch_interval = request.form.get("token_watch_interval", type=int)
      logging.info("set token_watch_interval to %s", token_watch_interval)
    return redirect(request.referrer)

  # set lease watch interval
  @app.route("/v1/sys/lease_watch_interval", methods=["POST"])
  def set_lease_watch_interval():
    global lease_watch_interval
    if "lease_watch_interval" in request.form:
      lease_watch_interval = request.form.get("lease_watch_interval", type=int)
      logging.info("set lease_watch_interval to %s", lease_watch_interval)
    return redirect(request.referrer)

  app.run(
    host  = '0.0.0.0',
    port = 80,
    #port  = 443,
    #ssl_context = ('certs/fullchain.pem', 'certs/privkey.pem'),
    debug = False
  )
