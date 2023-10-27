"""
This script will import a mapping of airline names to ICAO codes
and create a local DB cache. e.g. DAL -> Delta Air Lines
Airline data source: https://github.com/npow/airline-codes/blob/master/airlines.json
"""

import json
import re
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Load Postgres configs and credentials
POSTGRES_DB_NAME = os.getenv("POSTGRES_DB_NAME")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

# Connect the the flight db
flight_db = psycopg2.connect(
    database=POSTGRES_DB_NAME,
    host=POSTGRES_HOST,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    port=POSTGRES_PORT,
)
cursor = flight_db.cursor()

# Opening the JSON file and load to a Dict
with open(file="airlines.json", mode="r", encoding='UTF-8') as file:
    # Iterate through the airline code map and insert into the db
    airline_data = json.loads(file.read())
    for airline in airline_data:
        # Check to see if the airline info row contains a valid ICAO
        icao_regex = re.compile("^[a-zA-Z0-9]*$")
        contains_icao = icao_regex.match(airline["icao"])

        # If icao is found, add the the db
        if contains_icao:
            # INSERT OR REPLACE in case there are duplicates
            # For a production application, you'd want to create unique references
            # but for this, we'll just use the most recent record found.
            airline_icao = str(airline['icao']).lower()
            airline_name = str(airline['name']).replace("'", "''")
            airline_callsign = str(airline['callsign']).replace("'", "")
            airline_info = f"'{airline_icao}', '{airline_name}', '{airline_callsign}'"
            insert_query = " ".join([
                f"INSERT INTO airlines (icao, name, callsign) VALUES ({airline_info})",
                "ON CONFLICT (icao) DO NOTHING;"
            ])
            cursor.execute(insert_query)
        else:
            pass

# Print count of airline code records in the db
cursor.execute("SELECT * FROM airlines;")
airline_list = cursor.fetchall()
print(f"Added {len(airline_list)} airline codes")

# Save and close the db connection
flight_db.commit()
flight_db.close()
