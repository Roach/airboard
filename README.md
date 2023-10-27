
# Airboard

A simple Flask app to render ADS-B data as a flight scxhedule board

![Airboard](https://user-images.githubusercontent.com/32463/278677859-a2403542-ddf9-40c1-a4ac-b0c27971023d.png "Airboard")


This project uses ADS-B data captured by a PiAware node, which is hydrated with flight and airplane data from AeroAPI, then stored in a Railway Postgres database. 

To visualize recent air traffic, this project uses a simple Flask app hosted on Railway.

![Airboard Flowchart](https://user-images.githubusercontent.com/32463/277907321-1d6a2bf7-8431-45aa-a6ea-64df6657faa4.png "Airboard Flowchart")

This project has 2 main components:
 - `get_flights.py`
    
    A script which runs on a cron to fetch flight data from a local REST API provided by the PiAware

    This script fetched from the PiAware, checks to see if the flight data has alreadt been logged, and fetches additional flight data from AeroAPI before storing in Postgres.

- `main.py`

    This is the main Flask app. This app loads flight data from Postgres and renders a list page.

    This app also uses WorkOS to provide authentication.

