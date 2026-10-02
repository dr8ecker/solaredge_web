"""Opt-in test against a dedicated real Mosquitto broker, never a user's broker."""
import asyncio
import json
import os
import threading
import unittest
import uuid

import paho.mqtt.client as mqtt

from app.config import Config
from app.mqtt import MqttPublisher, SENSORS


@unittest.skipUnless(os.getenv('SEWEB_TEST_MQTT_HOST'), 'Dedicated test broker not configured')
class MqttIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_validity_reconnect_and_retained_shutdown(self):
        config = Config(mqtt_host=os.environ['SEWEB_TEST_MQTT_HOST'],plant_name='Test-'+uuid.uuid4().hex)
        publisher = MqttPublisher(config)
        received = {}
        lock = threading.Lock()
        observer = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='observer-'+uuid.uuid4().hex)
        def on_connect(client,userdata,flags,reason,properties):
            client.subscribe([(publisher.base+'/#',1),('homeassistant/sensor/+/config',1)])
        def on_message(client,userdata,message):
            with lock:
                received[message.topic] = message.payload.decode()
        observer.on_connect = on_connect
        observer.on_message = on_message
        observer.connect(config.mqtt_host,1883)
        observer.loop_start()
        async def until(predicate):
            deadline = asyncio.get_running_loop().time()+10
            while not predicate():
                if asyncio.get_running_loop().time()>deadline:
                    self.fail('Broker event timeout')
                await asyncio.sleep(.05)
        try:
            await publisher.start()
            await until(lambda:publisher.connected)
            publisher.update({'pv_energy_total':58.2,'grid_import_energy_total':5.29,
                              'grid_export_energy_total':50.2,'pv_power':1000,
                              'scraper_status':'connected'},solar_success=True)
            await until(lambda:received.get(publisher.base+'/state/pv_energy_total')=='58.2')
            topic='homeassistant/sensor/'+publisher.device_id+'_pv_energy_total/config'
            await until(lambda:topic in received)
            self.assertEqual(json.loads(received[topic])['state_class'],'total')
            await until(lambda:received.get(publisher.base+'/availability')=='online')
            await until(lambda:received.get(publisher.base+'/valid/grid_import_power')=='offline')
            self.assertNotIn(publisher.base+'/state/grid_import_power',received)
            # A new subscriber gets the retained values without another scrape.
            received.clear()
            observer.subscribe(publisher.base+'/#',qos=1)
            await until(lambda:received.get(publisher.base+'/state/pv_energy_total')=='58.2')
            await publisher.close()
            await until(lambda:received.get(publisher.base+'/connection')=='offline')
            await publisher.start()
            await until(lambda:received.get(publisher.base+'/connection')=='online')
            self.assertEqual(publisher.cache['pv_energy_total'],58.2)
            publisher.unavailable()
            await until(lambda:received.get(publisher.base+'/availability')=='offline')
            self.assertEqual(received[publisher.base+'/state/pv_energy_total'],'58.2')
        finally:
            await publisher.close()
            observer.disconnect()
            observer.loop_stop()
