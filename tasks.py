import json
import redis
import yaml
from celery import Celery
from heatpump import HeatPump

# Initialize Redis
app = Celery('tasks', broker='redis://redis:6379/0', backend='redis://redis:6379/0')
redis_client = redis.Redis(host='redis', port=6379, db=1)


@app.task
def heatpump():
    with open('registers.yaml', 'r') as file:
        config = yaml.safe_load(file)

    hp = HeatPump(config['settings'])
    hp.connect()
    data = hp.get_all_registers(config['registers'])
    redis_client.set('heatpump_data', str(json.dumps(data)))
    print(f"Registers saved to Redis: {len(data)}")

    # Initialise or invoke state changes
    state_data = redis_client.get('state_data')
    print(f"# State Data: {state_data}")
    if state_data is None:
        state_data = {
            'dhw_mode': data['power_on_off'][2]['value'],
            'zone_1_power': data['power_on_off'][1]['value'],
            'zone_2_power': data['power_on_off'][3]['value'],
            'setting_mode': data['setting_mode'][0]['value'],
            'zone_1_setpoint': data['flow_temps_set'][0]['value'],
            'zone_2_setpoint': data['flow_temps_set'][1]['value'],
            'dt1sh': data['dt1sh'][0]['value'],
            'oat': 10
        }
        redis_client.set('state_data', str(json.dumps(state_data)))
    else:
        state_data = json.loads(state_data)
        try:
            if state_data['dt1sh'] != data['dt1sh'][0]['value']:
                hp.set_dt1sh(int(state_data['dt1sh']))
        except KeyError:
            pass
        try:
            if state_data['zone_1_power'] != data['power_on_off'][1]['value']:
                hp.set_heating(state_data['zone_1_power'])
        except KeyError:
            pass
        try:
            if state_data['dhw_mode'] != data['power_on_off'][2]['value']:
                hp.set_dhw(state_data['dhw_mode'])
        except KeyError:
            pass
        try:
            if state_data['zone_1_setpoint'] != data['flow_temps_set'][0]['value']:
                hp.set_zone_1_setpoint(state_data['zone_1_setpoint'])
        except KeyError:
            pass


app.conf.beat_schedule = {
    'run-every-10-seconds': {
        'task': 'tasks.heatpump',
        'schedule': 10,
        'args': ()
    },
}
