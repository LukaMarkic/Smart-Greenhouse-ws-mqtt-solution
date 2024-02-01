import tornado.web
import tornado.websocket
import tornado.ioloop
from tornado.escape import json_encode
import MySQLdb as mdb
import json
import signal
import paho.mqtt.client as mqtt
import sys
import datetime

# Global variable for caching user data
user_data_cache = {}

# Connection details
hostname = "localhost"
mqtt_client = mqtt.Client()
con = None
frequencyOfDataStoring = 5
databaseConnectionData = {
    "address": "localhost",
    "host": 'root', 
    "password": 'new_password',
    "database": 'greenhouse'
}
settings = {
    "temperature": 60,
    "humidity": 100,
    "light": 100
}
topic_counter_mapping = {
    "data/temperature": frequencyOfDataStoring,
    "data/humidity": frequencyOfDataStoring,
    "data/light": frequencyOfDataStoring,
}
topic_table_mapping = {
    "data/temperature": {"table": "temperature_data", "value_table": "temperature"},
    "data/humidity": {"table": "humidity_data", "value_table": "humidity"},
    "data/light": {"table": "light_data", "value_table": "light"},
}

try:
    # Establish a connection to the MySQL database
    con = mdb.connect(databaseConnectionData["address"], databaseConnectionData["host"], databaseConnectionData["password"], databaseConnectionData["database"]) #"localhost", 'root', 'new_password', 'greenhouse'
    print("Connection to the database established successfully.")

except mdb.Error as e:
    print(f"Error connecting to the database: {e}")

class MainHandler(tornado.web.RequestHandler):
    client_id = None
    def get(self):
        user_data = user_data_cache.get(str(self.client_id))
        print(user_data)

        if user_data and self.client_id is not None:
            # User is logged in, render the dashboard with user data
            self.render("dashboard.html", username=user_data['username'], fullname=user_data['fullname'], userId=user_data['userId'])
        else:
            # User is not logged in, redirect to login page
            self.render("login.html")

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket opened")
        MainHandler.client_id = self.ws_connection.stream.socket.fileno()
        print(f"WebSocket opened for client: {MainHandler.client_id }")
        self.application.clients.add(self)

    def on_message(self, message):
        try:
            # Parse JSON message containing type and data
            data = tornado.escape.json_decode(message)
            message_type = data.get("type")
            message_data = data.get("data")
            
            print(f"Received message: {message_type} and {message_data}")

            if message_type == "login_data":
                # Handle login data
                username = message_data.get("username")
                password = message_data.get("password")
                print(f"uname: {username} and {password}")
                query = "SELECT * FROM users WHERE username = %s"
                print(MainHandler.client_id )
                with con.cursor() as cursor:
                    query = "SELECT * FROM users WHERE username = %s"
                    cursor.execute(query, (username,))

                    # Fetch the first row of table users(id, username, fullname, password)
                    user_data = cursor.fetchone()

                    if user_data and user_data[3] == password:
                        print("User found:")
                        print(f"Username: {user_data[1]}")
                        print(f"Fullname: {user_data[2]}")
                        
                        response_data = {
                            'type': 'login_success',
                            'data': {
                                'username': user_data[1],
                                'fullname': user_data[2],
                            }
                        }
                        
                        # Save user data to cache
                        user_data_cache[str(MainHandler.client_id)] = {
                            'username': user_data[1],
                            'fullname': user_data[2],
                            'userId': str(MainHandler.client_id)
                        }

                        # Redirect to the dashboard page
                        self.write_message(json_encode({'type': 'redirect', 'data': {'url': '/'}}))
                        self.redirect("/")
                    else:
                        print("User not found.")
            elif message_type == "mqtt_command":
                # Handle MQTT command
                topic = message_data.get("topic")
                payload = message_data.get("payload")

                if topic is not None and payload is not None:
                    # Publish the received data to the MQTT broker
                    mqtt_client.publish(topic, payload)
            elif message_type == "logout_command":
                # Handle logout command
                print(message_data.get("id"))
                if message_data.get("id") in user_data_cache:
                    del user_data_cache[message_data.get("id")]
                    self.write_message(json_encode({'type': 'redirect', 'data': {'url': '/'}}))
            elif message_type == "database_request":
                # Handle database request command
                topic = message_data.get("topic")
                timeSpan = message_data.get("timeSpan")
                with con.cursor() as cursor:
                    requested_data = get_data_from_database(cursor, topic, timeSpan)
                    requested_data_message = {
                    	"type": "database_requested_data",
                    	"payload": requested_data
                    }
                    requested_data_message_JSON = json_encode(requested_data_message)
                    self.write_message(requested_data_message_JSON)

            elif message_type == "setting_command":
                # Handle setting command
                settingKey = message_data.get("setting")
                payload = message_data.get("payload")
                print(settingKey)
                if settingKey:
                    # Try to parse payload to float
                    try:
                        payload_float = float(payload)
                    except ValueError:
                        print(f"Error: Unable to parse payload '{payload}' to float.")
                    else:
                        # If parsing is successful, update the setting value
                        settings[settingKey] = payload_float
                        mqtt_client.publish("setting/" + settingKey, payload)
                             
        except Exception as e:
            # Handle exceptions (e.g., database connection error)
            response_data = {'type': 'error', 'data': {'error': str(e)}}
            self.write_message(json_encode(response_data))


    def on_close(self):
        print("WebSocket closed")
        self.application.clients.remove(self)

class Application(tornado.web.Application):
    def __init__(self):
        self.clients = set()
        self.mqtt_messages = []
        super(Application, self).__init__([
            (r"/", MainHandler),
            (r"/ws", WebSocketHandler),
        ])

    def send_mqtt_messages(self):
        for client in self.clients:
            try:
                # Send pending MQTT messages to connected WebSocket clients
                for msg in self.mqtt_messages:
                    client.write_message(msg)
                self.mqtt_messages.clear()
            except tornado.websocket.WebSocketClosedError:
                print("WebSocket closed. Removing from active clients.")
                self.clients.remove(client)

def sendAlarmMessage(topic, payload):
    # Get the last word after "/"
    setting = topic.split("/")[-1]
    sufix = "%"
    if setting == "temperature":
        sufix = " °C"

    # Access the corresponding setting value
    if setting in settings:
        setting_value = settings[setting]
        # Parse payload to float
        try:
            payload_value = float(payload)
        except ValueError:
            print("Error: Payload value is not a valid float.")
            return
        
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg_data = {
            'type': 'notification_message',
            'data': {
                'title': "The value of " + setting + " is to high!",
                'payload': "The value of " + setting + " is: " + str(payload) + sufix + ", but it should be: " + str(setting_value) + sufix + ".",
                'time': current_datetime
            }
        }

        if payload_value > setting_value:
            # Send WebSocket message ("Alarm")
            application.mqtt_messages.append(json.dumps(msg_data))

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker")
    client.subscribe("data/humidity")
    client.subscribe("data/temperature")
    client.subscribe("data/light")

def on_message(client, userdata, msg):
    print(f"Received MQTT message: {msg.payload}")
    current_datetime = datetime.datetime.now()
    handle_topic(msg.topic, msg.payload, current_datetime)

    sendAlarmMessage(msg.topic, msg.payload.decode('utf-8'))
    msg_data = {
    	'type': 'sensors_data',
    	'data': {
        	'topic': msg.topic,
        	'payload': msg.payload.decode('utf-8')
        	}
    }
    application.mqtt_messages.append(json.dumps(msg_data))

def update_last_save_time(current_datetime):
    global last_save_time
    last_save_time = current_datetime
    print(f"Last save time updated to: {last_save_time}")
    
def handle_topic(topic, payload, current_datetime):
    if topic in topic_table_mapping:
        table_info = topic_table_mapping[topic]
        value = float(payload)
        increment_counter(topic)
        if topic_counter_mapping[topic] >= frequencyOfDataStoring:
            insert_data(current_datetime, table_info["table"], table_info["value_table"], value)
            reset_counter(topic)
    else:
        print(f"Error: Topic {topic} not mapped to any table.")

def increment_counter(topic):
    topic_counter_mapping[topic] += 1

def reset_counter(topic):
    topic_counter_mapping[topic] = 0

def fetch_and_format(cursor, query, valueTable):
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    data = cursor.fetchall()
    result = []
    
    for row in data:
        date_str = row[1].strftime("%Y-%m-%d")
        time_str = str(row[2]) 
        value = float(row[3])
        
        result.append({"date": date_str, "time": time_str, f"{valueTable}": value})
    
    return result

# Function to get data based on timeSpan or specific date for a given table
def get_data_from_database(cursor, topic, timeSpan):
    table_name = topic_table_mapping[topic]["table"]
    valueTable = topic_table_mapping[topic]["value_table"]
    if timeSpan == "today":
        return fetch_and_format(cursor, f"SELECT * FROM {table_name} WHERE date = CURDATE()", valueTable)
    elif timeSpan == "lastDay":
        return fetch_and_format(cursor, f"SELECT * FROM {table_name} WHERE date = CURDATE() - INTERVAL 1 DAY", valueTable)
    elif timeSpan == "lastWeek":
        return fetch_and_format(cursor, f"SELECT * FROM {table_name} WHERE date BETWEEN CURDATE() - INTERVAL 7 DAY AND CURDATE()", valueTable)
    elif timeSpan == "lastMonth":
        return fetch_and_format(cursor, f"SELECT * FROM {table_name} WHERE date BETWEEN CURDATE() - INTERVAL 1 MONTH AND CURDATE()", valueTable)
    elif timeSpan == "allTime":
        return fetch_and_format(cursor, f"SELECT * FROM {table_name}", valueTable)
    elif len(timeSpan) == 10:  # Check if the length is 10 characters (YYYY-MM-DD)
        return fetch_and_format(cursor, f"SELECT * FROM {table_name} WHERE date = '{timeSpan}'", valueTable)
    else:
        return []

def insert_data(current_datetime, table_name, value_table_name, value):
    try:
        # Connect to the database
        with con.cursor() as cursor:
            # Create a cursor object to interact with the database
            query = "INSERT INTO "+ table_name +  " (date, time, "+ value_table_name +") VALUES (%s, %s, %s)"
            cursor.execute(query, (current_datetime.date(), current_datetime.time(), value))
            con.commit()
        print(f"Data inserted into the database: " + table_name + " at {current_datetime} - {value}°C")

    except Exception as e:
        print(f"Error inserting data into the database: {e}")

def signal_handler(signum, frame):
    print("Received termination signal. Stopping server.")
    tornado.ioloop.IOLoop.current().stop()
    
# Register the signal handler for termination signal (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(hostname, 1883, 60)
mqtt_client.loop_start()

application = Application()

# Periodically check for MQTT messages and send them to connected clients
mqtt_callback = tornado.ioloop.PeriodicCallback(application.send_mqtt_messages, 1000)
mqtt_callback.start()

if __name__ == "__main__":
    application.listen(8888)
    print("Server is running on http://" + hostname + ":8888")
    tornado.ioloop.IOLoop.current().start()

