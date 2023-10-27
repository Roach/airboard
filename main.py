import os
import json
from datetime import timedelta
from dotenv import load_dotenv
import workos
import psycopg2
import psycopg2.extras
from whitenoise import WhiteNoise
from flask import (Flask, redirect, render_template, make_response, request, url_for)
from flask_jwt_extended import create_access_token, jwt_required, set_access_cookies, JWTManager

# Server configs
DEBUG=False
app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root="static/", prefix="static/")
jwt = JWTManager(app)


# Load variables from .env
load_dotenv()

# WorkOS SSO setup
workos.base_api_url = 'http://localhost:3000/' if DEBUG else workos.base_api_url
workos.api_key = os.getenv('WORKOS_API_KEY')
workos.client_id = os.getenv('WORKOS_CLIENT_ID')
CUSTOMER_EMAIL_DOMAIN = os.getenv('WORKOS_CUSTOMER_EMAIL_DOMAIN')
CUSTOMER_CONNECTION_ID = os.getenv('WORKOS_CUSTOMER_CONNECTION_ID')

# Flask-JWT setup
app.config["JWT_SECRET_KEY"] = workos.api_key
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=5)
app.config["JWT_COOKIE_SECURE"] = False


# Load flight data
def get_recent_flights():
    """
    Get the 10 most recent flight recordss from the database
    """

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
    cursor = flight_db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    flights_query = """
        SELECT flight_id, ident_icao, registration, operator_icao, operator_callsign, flight_number, origin_city, origin_iata, dest_city, dest_iata, aircraft_type, aircraft_manufacturer, aircraft_model, timestamp
        FROM flights order by timestamp desc limit 10;
    """
    cursor.execute(flights_query)
    recent_flights = cursor.fetchall()
    dict_result = []
    for row in recent_flights:
        dict_result.append(dict(row))
    flight_db.close()
    return dict_result

# Redirect to login page if no auth cookie found
@jwt.unauthorized_loader
def custom_unauthorized_response(_err):
    """
    Redirect back to login page on auth error
    """
    return redirect(url_for('login'))

# Main login page route
@app.route('/')
@jwt_required()
def main():
    """
    Redirect root to the main flights path
    """
    return redirect(url_for('flights'))

# Healthcheck route
@app.route('/health')
def health():
    """
    Redirect root to the main flights path
    """
    return make_response(json.dumps({'message': 'Hello Railway!'}), 200)


# Show main login page
@app.route('/login')
def login():
    """
    Render login template
    """
    return render_template('login.html')

# OAuth redirect route
@app.route('/auth')
def auth():
    """
    WorkOS OAuth redirect
    """
    authorization_url = workos.client.sso.get_authorization_url(
        domain = CUSTOMER_EMAIL_DOMAIN,
        redirect_uri = url_for('auth_callback', _external=True),
        state = {},
        connection = CUSTOMER_CONNECTION_ID
    )

    return redirect(authorization_url)

# OAuth code exchange route
@app.route('/auth/callback')
def auth_callback():
    """
    OAuth code exchange - Get profile context from WorkOS
    """
    code = request.args.get('code')
    profile = workos.client.sso.get_profile_and_token(code)
    p_profile = profile.to_dict()
    user_email = p_profile['profile']['email']

    # Redirect to /protected on successful login
    resp = make_response(redirect(url_for('flights')))

    # Create JWT token and set cookie
    access_token = create_access_token(identity=user_email)
    set_access_cookies(response=resp, encoded_access_token=access_token)
    return resp

# Flight board route
@app.route("/flights", methods=["GET"])
@jwt_required()
def flights():
    """
    Show airplane list
    Requires a valid JWT for auth
    """
    flight_list = get_recent_flights()
    return flask.render_template('flights.html', flights=flight_list)

# Start Flask
if __name__ == '__main__':
    app.run(debug=False, port=3000)
