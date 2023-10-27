"""
Load flight data from AeroAPI and save into Postgres DB, runs as a cron job
"""
import os
import sqlite3
from datetime import datetime, timedelta
import httpx
import psycopg2
from dotenv import load_dotenv

# Load vars from .env
load_dotenv()

# AeroAPI and PiAware
AEROAPI_KEY = os.getenv("AEROAPI_KEY")
AEROAPI_HOST = "https://aeroapi.flightaware.com"
PIAWARE_URI = "http://192.168.0.29/skyaware/data/aircraft.json"

# Load Postgres configs and credentials
POSTGRES_DB_NAME = os.getenv("POSTGRES_DB_NAME")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

def get_planes():
    """
    Get airplane list from PiAware endpoint
    """
    planes_response = httpx.get(PIAWARE_URI)
    airplane_list = planes_response.json().get('aircraft')

    # Filter flights without a flight number
    for airplane in airplane_list:
        if 'flight' in airplane:
            flight_number = airplane['flight'].strip()
            # Check the DB for this flight and pass if found, otherwise call AeroAPI
            if get_flight_record(flight_number):
                print(f"Flight found: {flight_number}")
            else:
                print(f"Flight not found: {flight_number}")
                flight_info = get_flight_info(flight_number)
                print(flight_info)
                # If AeroAPI returns data, add the flight to the DB, otherwise skip
                if flight_info:
                    add_recent_flight(flight_info)
                else:
                    pass

def get_airplane_info(airplane_type):
    """
    Call AeroAPI's flight lookup API to get airplane metadata from the 
    airplane type provided by PiAware
    """
    # Construct the AeroAPI request
    aeroapi_uri = f"{AEROAPI_HOST}/aeroapi/aircraft/types/{airplane_type}"
    aeroapi_headers = {
        'x-apikey':AEROAPI_KEY
    }

    # Fetch the flight data from AeroAPI and return the latest result
    airplane_info = httpx.get(
        aeroapi_uri,
        headers=aeroapi_headers,
    ).json()
    return airplane_info if airplane_info else None


def get_flight_info(flight_number):
    """
    Call AeroAPI's flight lookup API to get flight metadata from the 
    flight number provided by PiAware
    """
    # Generate range timestamps
    now_ts = datetime.now()
    now = now_ts.strftime("%Y-%m-%d")
    tomorrow_ts = now_ts + timedelta(days=+1)
    tomorrow = tomorrow_ts.strftime("%Y-%m-%d")

    # Construct the AeroAPI request
    aeroapi_uri = f"{AEROAPI_HOST}/aeroapi/flights/{flight_number}"
    aeroapi_headers = {
        'x-apikey':AEROAPI_KEY
    }
    aeroapi_params = {
        'ident_type':'fa_flight_id',
        'start': now,
        'end': tomorrow
    }

    # Fetch the flight data from AeroAPI and return the latest result
    flight_list = httpx.get(
        aeroapi_uri,
        headers=aeroapi_headers,
        params=aeroapi_params
    ).json().get('flights')
    ident_icao = flight_list[0]['ident_icao'] if flight_list else None
    # If the AeroAPI returned an airline icao, then it's a commercial flight, store it
    if ident_icao:
        flight_info = flight_list[0]
        airplane_info = get_airplane_info(flight_info['aircraft_type'])
        flight_record = {
            'flight_id': flight_info['inbound_fa_flight_id'],
            'ident_icao': flight_info['ident_icao'],
            'registration': flight_info['registration'],
            'aircraft_type': airplane_info['type'],
            'aircraft_manufacturer': airplane_info['manufacturer'],
            'aircraft_model': airplane_info['type'],
            'operator_icao': flight_info['operator_icao'],
            'operator_callsign': get_airline_callsign(flight_info['operator_icao']),
            'flight_number': flight_info['flight_number'],
            'origin_city': flight_info['origin']['city'],
            'origin_iata': flight_info['origin']['code_iata'],
            'dest_city': flight_info['destination']['city'],
            'dest_iata': flight_info['destination']['code_iata'],
            'timestamp': datetime.now().strftime('%s')
        }
    return flight_record if flight_record else None

def add_recent_flight(flight_record):
    # """
    # Add a flight record to the DB, using the flight_record object constructed above
    # """

    """
        flight_id,	
        ident_icao,
        registration,
        operator_icao,
        operator_callsign,
        flight_number,
        origin_city,
        origin_iata,
        dest_city,
        dest_iata,
        aircraft_type,
        aircraft_manufacturer,
        aircraft_model,
        timestamp
    """

    # Connect the the flight db
    flight_db = psycopg2.connect(
        database=POSTGRES_DB_NAME,
        host=POSTGRES_HOST,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        port=POSTGRES_PORT,
    )
    cursor = flight_db.cursor()

    # These named placeholders need to match the keys in the flight_record Dict
    cursor.execute(
        f"""INSERT INTO flights (
            flight_id,	
            ident_icao,
            registration,
            operator_icao,
            operator_callsign,
            flight_number,
            origin_city,
            origin_iata,
            dest_city,
            dest_iata,
            aircraft_type,
            aircraft_manufacturer,
            aircraft_model,
            timestamp
        ) VALUES (
            '{flight_record['flight_id']}',	
            '{flight_record['ident_icao']}',
            '{flight_record['registration']}',
            '{flight_record['operator_icao']}',
            '{flight_record['operator_callsign']}',
            '{flight_record['flight_number']}',
            '{flight_record['origin_city']}',
            '{flight_record['origin_iata']}',
            '{flight_record['dest_city']}',
            '{flight_record['dest_iata']}',
            '{flight_record['aircraft_type']}',
            '{flight_record['aircraft_manufacturer']}',
            '{flight_record['aircraft_model']}',
            NOW()
        ) ON CONFLICT (flight_id) DO NOTHING;;
        """
    )
    flight_db.commit()
    flight_db.close()

def get_flight_record(flight_number):
    """
    Query the DB for a specific flight number and return
    """

    # Connect the the flight db
    flight_db = psycopg2.connect(
        database=POSTGRES_DB_NAME,
        host=POSTGRES_HOST,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        port=POSTGRES_PORT,
    )
    cursor = flight_db.cursor()
    recent_flights = cursor.execute(
        f"SELECT * FROM flights where flight_number = '{flight_number}';"
    )
    flight_data = recent_flights.fetchone() if recent_flights else None
    flight_db.commit()
    flight_db.close()
    return flight_data

def get_airline_callsign(icao):
    """
    Cross reference icao code (e.g. DAL) to get airline callsign string (e.g. Delta)
    Cretaed a local table with this mapping to reduce calls    
    """
    airline_db = sqlite3.connect("flights.db")
    airline_db.row_factory = sqlite3.Row
    airline_callsigns = airline_db.execute(
        f"SELECT * FROM airlines WHERE icao = '{icao}';"
    ).fetchall()
    airline_db.close()

    if airline_callsigns:
        return airline_callsigns[0]['callsign']
    else:
        return 'N/A'

#     
get_planes()
