import json
import redis
import pymodbus.client as ModbusClient
from pymodbus import Framer


class HeatPump:

    client: ModbusClient.ModbusTcpClient
    config: dict

    def __init__(self, config):
        self.config = config

    def get_state_keys(self):
        state_data = [
            'dhw_mode',
            'zone_1_power',
            'zone_2_power',
            'setting_mode',
            'zone_1_setpoint',
            'zone_2_setpoint',
            'dt1sh',
            'oat'
        ]
        return state_data

    def connect(self):
        self.client = ModbusClient.ModbusTcpClient(
            host=self.config['ip_address'],
            port=self.config['port'],
            framer=Framer.RTU
        )
        self.redis_client = redis.Redis(host='redis', port=6379, db=1)

    def read_register(self, number, count=1):
        while 1:
            try:
                response = self.client.read_holding_registers(
                    number,
                    count,
                    unit=self.config['slave_id']
                )
                response.registers[0]
                return response
            except:
                if response.isError():
                    print(f"Error reading register {number}: {response}")
                pass


    def read_16bit_split_register(self, number, count=1):
        while 1:
            try:
                result = self.client.read_holding_registers(
                    number,
                    count,
                    unit=self.config['slave_id']
                )
                # Extract the register value (16-bit integer)
                register_value = result.registers[0]
                print(f"Raw 16-bit register value: {register_value}")

                # Extract low and high bytes
                low_byte = register_value & 0xFF  # Bits 0-7 (low byte)
                high_byte = (register_value >> 8) & 0xFF  # Bits 8-15 (high byte)

                return low_byte, high_byte

            except:
                if result.isError():
                    print(f"Error reading register {number}: {result}")
                pass

    def read_register_bit(self, number, count, bit):
        try:
            response = self.client.read_holding_registers(
                number,
                count,
                unit=self.config['slave_id']
            )

            print("Register values:", response.registers)
            register_value = response.registers[0]
            value = (register_value >> bit) & 0x01
            return value
        except:
            if response.isError():
                print(f"Error reading register: {number}")
            pass

    def get_all_registers(self, registers):
        data = {}
        for register in registers:
            response = self.read_register(
                number=register['number'],
                count=register['count']
            )

            if response is not None:
                if 'bits' in register.keys() and register['count'] == 1:
                    register_value = response.registers[0]
                    bit_list = list()
                    for bit in register['bits']:
                        bit_list.append(
                            {
                                'value': (register_value >> bit) & 0x01,
                                'register': register['number'],
                                'count': register['count'],
                                'bit': bit,
                                'name': register['bits'][bit]
                            }
                        )

                    data[register['name']] = bit_list

                elif 'options' in register.keys() and register['count'] == 1:
                    try:
                        data[register['name']] = [{
                            'value': register['options'][response.registers[0]],
                            'register': register['number'],
                            'count': register['count']
                        }]
                    except:
                        print(f"[FAILED] Processing options list - {register['number']} - {register['options']}")
                        pass
                elif 'split' in register.keys() and register['count'] == 1:
                    register_value = response.registers[0]
                    # Extract low and high bytes
                    low_byte = register_value & 0xFF  # Bits 0-7 (low byte)
                    high_byte = (register_value >> 8) & 0xFF  # Bits 8-15 (high byte)
                    data[register['name']] = [{
                        'value': low_byte,
                        'register': register['number'],
                        'count': register['count'],
                        'name': register['split']['low']
                    },{
                        'value': high_byte,
                        'register': register['number'],
                        'count': register['count'],
                        'name': register['split']['high']
                    }]

                elif register['count'] == 1:
                    data[register['name']] = [{
                        'value': response.registers[0],
                        'register': register['number'],
                        'count': register['count']
                    }]

        return data

    def write_16bit_split_register(self, number, value1, value2, count=1):

        combined_value = (value2 << 8) | value1
        write_response = self.client.write_register(
            number,
            combined_value,
            unit=self.config['slave_id']
        )
        # Check if the write operation was successful
        if write_response.isError():
            print("Error writing to register.")
            return 1
        else:
            print(f"Successfully wrote combined value {combined_value} to register {number}")

    def _write_single_register(self, register, value):
        write_response = self.client.write_register(
            register,
            value,
            unit=self.config['slave_id']
        )
        if write_response.isError():
            print(f"Error writing new value to register: {write_response}")
            return {
                'status': f"Failed",
                'value': value,
                'register': register
            }
        else:
            print(f"New value written to register: {register}")
            return {
                'status': f"Success",
                'value': value,
                'register': register
            }

    def turn_on_heating(self):
        return self._write_single_register(0, 1 << 1)

    def turn_off_heating(self):
        return self._write_single_register(0, 1 << 0)

    def turn_on_dhw(self):
        return self._write_single_register(0, 2 << 1)

    def turn_off_dhw(self):
        return self._write_single_register(0, 2 << 0)

    def set_dt1sh(self, value):
        self._write_single_register(229, value)

    def set_dhw(self, value):
        if value == 1:
            return self._write_single_register(0, 2 << 1)
        elif value == 0:
            return self._write_single_register(0, 2 << 0)

    def set_heating(self, value):
        if value == 1:
            return self._write_single_register(0, 1 << 1)
        elif value == 0:
            return self._write_single_register(0, 1 << 0)

    def set_zone_1_setpoint(self, value):
        # Get current zone values
        data = json.loads(self.redis_client.get('heatpump_data'))
        zone1 = data['flow_temps_set'][0]['value']
        zone2 = data['flow_temps_set'][1]['value']
        if int(zone1) != int(value):
            self.write_16bit_split_register(2, int(value), int(zone2))
