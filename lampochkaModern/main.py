import threading
import atexit
from typing import Optional
import datetime
import json
import os

from flask import Flask, render_template, request, Response, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound, MultipleResultsFound, OperationalError
from mqtt.client import mqtt_client


POOL_TIME = 10
timerThread: Optional[threading.Timer] = None
db_create_flag = False
root_dir = os.path.dirname(os.path.abspath(__file__))
configs = None
db_session: Optional[Session] = None
Schedule: Optional[object] = None


def get_configs():
    configs_path = os.path.join(root_dir, 'settings.json')
    with open(configs_path, 'rt') as file:
        cfg = json.loads(file.read())
    return cfg


def create_app():
    app = Flask(__name__, static_url_path='/static/', static_folder='static')

    def interrupt():
        global timerThread
        if timerThread is not None:
            timerThread.cancel()

    def periodic_tack():
        global timerThread
        global db_session

        # print('PERIODIC TASK', previous_time)

        now = datetime.datetime.now().time()
        schedule = None

        # Выключение
        has_to_clear = False
        now_ts = datetime.time(now.hour, now.minute)

        try:
            schedule = db_session.query(Schedule).filter_by(end_time=now_ts).one()
            has_to_clear = True
        except MultipleResultsFound:
            has_to_clear = True
        except NoResultFound:
            pass

        if has_to_clear:
            rng = f'[{configs["MQTT_CLIENT"]["MIN_LINE_VALUE"]},{configs["MQTT_CLIENT"]["MAX_LINE_VALUE"]}]'
            topic = f'{configs["MQTT_CLIENT"]["DEVICE_TYPE"]}/{configs["MQTT_CLIENT"]["SERIAL_NUMBER"]}/{configs["MQTT_CLIENT"]["DEVICE_TOPIC"]}/2/{rng}'
            payload = {'red': 0, 'green': 0, 'blue': 0}
            mqtt_client.publish(topic, json.dumps(payload, indent=2).replace(': ', ':'))

        # Включение
        has_to_turn_on = False
        now_ts = datetime.time(now.hour, now.minute)

        try:
            schedule = db_session.query(Schedule).filter_by(start_time=now_ts).one()
            has_to_turn_on = True
        except MultipleResultsFound:
            has_to_turn_on = True
        except NoResultFound:
            pass

        if has_to_turn_on and schedule:
            rng = f'[{configs["MQTT_CLIENT"]["MIN_LINE_VALUE"]},{configs["MQTT_CLIENT"]["MAX_LINE_VALUE"]}]'
            topic = f'{configs["MQTT_CLIENT"]["DEVICE_TYPE"]}/{configs["MQTT_CLIENT"]["SERIAL_NUMBER"]}/{configs["MQTT_CLIENT"]["DEVICE_TOPIC"]}/2/{rng}'
            red = int(schedule.color[1:3], 16)
            green = int(schedule.color[3:5], 16)
            blue = int(schedule.color[5:7], 16)
            payload = {'red': red, 'green': blue, 'blue': green}
            mqtt_client.publish(topic, json.dumps(payload, indent=2).replace(': ', ':'))

        # таймер одноразовый, приходится перезапускать его изнутри функции, как setTimeout
        timerThread = threading.Timer(POOL_TIME, periodic_tack, ())
        timerThread.start()

    def periodic_task_start():
        global timerThread
        timerThread = threading.Timer(POOL_TIME, periodic_tack, ())
        timerThread.start()

    periodic_task_start()
    atexit.register(interrupt)
    return app


def create_db(app: Flask):
    db = SQLAlchemy(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    return db


server_app = create_app()
server_db = create_db(server_app)
db_session: Session = server_db.session
configs = get_configs()


class Schedule(server_db.Model):
    id = server_db.Column(server_db.Integer, primary_key=True)
    start_time = server_db.Column(server_db.Time, nullable=False)
    end_time = server_db.Column(server_db.Time, nullable=False)
    color = server_db.Column(server_db.String(20), nullable=False)


try:
    _ = db_session.query(Schedule).filter_by().one()
except (MultipleResultsFound, NoResultFound):
    pass
except OperationalError:
    server_db.create_all()


@server_app.route('/')
def index():
    return render_template("index.html")


@server_app.route('/schedule/add', methods=['POST'])
def schedule_add():
    color = request.form['exampleColorInput']
    start_time_str = request.form['startWork']
    end_time_str = request.form['endWork']

    start_time = datetime.time(int(start_time_str[0:2]), int(start_time_str[3:5]), 0)
    end_time = datetime.time(int(end_time_str[0:2]), int(end_time_str[3:5]), 0)

    schedule = Schedule(start_time=start_time, end_time=end_time, color=color)
    db_session.add(schedule)
    db_session.commit()
    db_session.flush()

    db_session.refresh(schedule)
    return redirect('/')


@server_app.route('/schedule/delete/<int:schedule_id>', methods=['DELETE'])
def schedule_delete(schedule_id):
    schedule = Schedule.query.filter_by(id=schedule_id).one()
    db_session.delete(schedule)
    db_session.commit()
    return redirect('/')


@server_app.route('/schedule/list', methods=['GET'])
def schedule_list():
    schedules = db_session.query(Schedule).all()
    response = [{
        'id': s.id,
        'color': s.color,
        'startTime': str(s.start_time)[:5],
        'endTime': str(s.end_time)[:5],
    } for s in schedules]
    return redirect('/')


if __name__ == '__main__':
    mqtt_client.connect()
    server_app.run()
