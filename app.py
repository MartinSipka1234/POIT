import time
import threading
import csv
import os
from flask import Flask, render_template, jsonify, request, send_file
import serial

app = Flask(__name__)

# Initialize serial connection
def initialize_serial():
    try:
        ser = serial.Serial('COM8', 9600)  # Adjust the port for your computer
        print("Serial port initialized on COM8")
        return ser
    except serial.SerialException as e:
        print(f"Failed to initialize serial port on COM8: {e}")
        return None

ser = initialize_serial()

monitoring_settings = {
    "interval": 5000,  # Default reading interval in milliseconds
}

data = []
start_time = None
current_time = 0
monitoring_thread = None
monitoring_active = False
archive_file = 'data_archive.csv'


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})
    if file:
        filename = 'uploaded_data.csv'
        file.save(filename)
        return jsonify({'status': 'success', 'message': 'File uploaded successfully'})
    return jsonify({'status': 'error', 'message': 'File upload failed'})


def read_data():
    global start_time, current_time, monitoring_active
    if start_time is None:
        start_time = time.time()
    print("read_data function started")
    while monitoring_active:
        if ser and ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').rstrip()
            print(f"Raw data from sensor: {line}")
            try:
                values = [float(x) for x in line.split(',')]
                timestamp = round(time.time() - start_time + current_time, 1)
                if len(values) == 6:
                    data_point = {
                        'timestamp': timestamp,
                        'accel_x': values[0],
                        'accel_y': values[1],
                        'accel_z': values[2],
                        'gyro_x': values[3],
                        'gyro_y': values[4],
                        'gyro_z': values[5]
                    }
                    data.append(data_point)
                    print(f"Parsed data: {data[-1]}")
                    write_to_csv(data_point)
            except ValueError:
                print(f"Failed to convert '{line}' to float")
        else:
            print("No data in waiting")
        time.sleep(monitoring_settings['interval'] / 1000)

def write_to_csv(data_point):
    with open(archive_file, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data_point.keys())
        if file.tell() == 0:
            writer.writeheader()
        writer.writerow(data_point)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/open', methods=['POST'])
def open_connection():
    try:
        if ser:
            ser.write(b'OPEN')
            time.sleep(2)
            print("Connection opened and sensors activated")
            return jsonify({'status': 'success', 'message': 'Connection opened and sensors activated'})
        else:
            return jsonify({'status': 'error', 'message': 'Serial port is not initialized'})
    except Exception as e:
        print(f"Error in /open: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/settings', methods=['POST', 'GET'])
def settings():
    global monitoring_settings
    if request.method == 'POST':
        try:
            data = request.get_json()
            monitoring_settings['interval'] = int(data['interval'])
            print(f"Updated settings: {monitoring_settings}")
            return jsonify({'status': 'success', 'message': 'Settings updated'})
        except Exception as e:
            print(f"Error in /settings POST: {e}")
            return jsonify({'status': 'error', 'message': str(e)})
    elif request.method == 'GET':
        print(f"Current settings: {monitoring_settings}")
        return jsonify(monitoring_settings)

@app.route('/start', methods=['POST'])
def start_monitoring():
    global monitoring_thread, monitoring_active, start_time, current_time
    try:
        if ser:
            ser.write(b'START')
            monitoring_active = True
            if monitoring_thread is None or not monitoring_thread.is_alive():
                monitoring_thread = threading.Thread(target=read_data)
                monitoring_thread.start()
                print("Monitoring thread started")
            print("Monitoring started")
            return jsonify({'status': 'success', 'message': 'Monitoring started'})
        else:
            return jsonify({'status': 'error', 'message': 'Serial port is not initialized'})
    except Exception as e:
        print(f"Error in /start: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/stop', methods=['POST'])
def stop_monitoring():
    global monitoring_active, current_time, start_time
    try:
        monitoring_active = False
        if start_time:
            current_time += time.time() - start_time
            start_time = None
        print("Monitoring stopped")
        return jsonify({'status': 'success', 'message': 'Monitoring stopped'})
    except Exception as e:
        print(f"Error in /stop: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/reset', methods=['POST'])
def reset_data():
    global data, start_time, current_time
    try:
        data = []
        start_time = None
        current_time = 0
        if os.path.exists(archive_file):
            os.remove(archive_file)
        print("Data reset")
        return jsonify({'status': 'success', 'message': 'Data reset'})
    except Exception as e:
        print(f"Error in /reset: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/data', methods=['GET'])
def get_data():
    try:
        if data:
            latest_data = data[-1]
            print(f"Sending latest data: {latest_data}")
            return jsonify(latest_data)
        else:
            print("No data to send")
            return jsonify({'timestamp': 0, 'accel_x': 0, 'accel_y': 0, 'accel_z': 0, 'gyro_x': 0, 'gyro_y': 0, 'gyro_z': 0})
    except Exception as e:
        print(f"Error in /data: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/archive', methods=['GET'])
def get_archive():
    try:
        return send_file(archive_file, as_attachment=True)
    except Exception as e:
        print(f"Error in /archive: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/close', methods=['POST'])
def close_connection():
    global ser
    try:
        if ser:
            ser.close()
            print("Serial port closed")
            ser = initialize_serial()
            return jsonify({'status': 'success', 'message': 'Serial port closed'})
        else:
            return jsonify({'status': 'error', 'message': 'Serial port is not open'})
    except Exception as e:
        print(f"Error in /close: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
