web: waitress-serve --listen=0.0.0.0:$PORT --max-request-body-size=8388608 --max-request-header-size=32768 --channel-timeout=60 --connection-limit=100 wsgi:app
