import yaml
import redis
import json
from fastapi import FastAPI, Request
from heatpump import HeatPump

app = FastAPI()

with open('registers.yaml', 'r') as file:
    config = yaml.safe_load(file)

hp = HeatPump(config['settings'])
hp.connect()

redis_client = redis.Redis(host='redis', port=6379, db=1)

@app.get("/")
async def read_root():
    return {
        'api_list':
        [
            {
                'path': '/get/all',
                'method': 'GET'
            },
            {
                'path': '/get/core',
                'method': 'GET'
            },
            {
                'path': '/get/state',
                'method': 'GET'
            }
        ]
    }

@app.get("/get/all")
async def get_all():
    try:
        data = json.loads(redis_client.get('heatpump_data'))
        return data
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}

@app.get("/get/state")
async def get_state():
    try:
        data = json.loads(redis_client.get('state_data'))
        return data
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}


@app.get("/action/turn-on-heating")
async def action_turn_on_heating():
    hp.turn_on_heating()


@app.get("/action/turn-off-heating")
async def action_turn_off_heating():
    hp.turn_off_heating()


@app.get("/action/turn-on-dhw")
async def action_turn_on_dhw():
    hp.turn_on_dhw()


@app.get("/action/turn-off-dhw")
async def action_turn_off_dhw():
    hp.turn_off_dhw()


@app.post("/action/set-state")
async def action_set_state(request: Request):
    req_data = await request.json()
    state_data = json.loads(redis_client.get('state_data'))

    print(req_data)
    state_keys = hp.get_state_keys()
    for item in req_data:
        if item in state_keys:
            state_data[item] = req_data[item]

    redis_client.set('state_data', json.dumps(state_data))
    return json.dumps(state_data)
