import paho.mqtt.client as mqtt
import random
import string
import os
import json


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_configs():
    configs_path = os.path.join(root_dir, 'settings.json')
    with open(configs_path, 'rt') as file:
        cfg = json.loads(file.read())
    return cfg


configs = get_configs()


class MqttClient(mqtt.Client):
    client_suffix = ''.join(random.sample(string.ascii_uppercase, 8))
    client_mqtt_status_topic = f'status/service/{configs["MQTT_CLIENT"]["CLIENT_ID_PREFIX"]}/{client_suffix}/state'

    def __init__(self, *args, **kwargs):
        if "client_id" not in kwargs.keys():
            kwargs["client_id"] = f'service::{configs["MQTT_CLIENT"]["CLIENT_ID_PREFIX"]}_{self.client_suffix}'
        super(MqttClient, self).__init__(*args, **kwargs)

    def connect(self, *args, **kwargs):
        if "host" not in kwargs.keys():
            kwargs["host"] = configs["MQTT_CLIENT"]["HOST"]
        if "port" not in kwargs.keys():
            kwargs["port"] = configs["MQTT_CLIENT"]["PORT"]
        kwargs["keepalive"] = kwargs.get("keepalive", 30)
        self.username_pw_set(username=configs["MQTT_CLIENT"]["USERNAME"], password=configs["MQTT_CLIENT"]["PASSWORD"])
        self.will_set(topic=self.client_mqtt_status_topic, payload='', retain=True)
        super(MqttClient, self).connect(*args, **kwargs)


mqtt_client = MqttClient(clean_session=False)
