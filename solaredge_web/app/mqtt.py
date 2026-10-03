"""MQTT Discovery, retained values, per-field validity, LWT and reconnect."""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

import paho.mqtt.client as mqtt

from .energy import identity

LOGGER = logging.getLogger(__name__)

# key -> German display name, device class, state class, unit
SENSORS = {
    'pv_power': ('PV-Leistung', 'power', 'measurement', 'W'),
    'consumption_power': ('Hausverbrauch', 'power', 'measurement', 'W'),
    'grid_import_power': ('Netzbezug Leistung', 'power', 'measurement', 'W'),
    'grid_export_power': ('Netzeinspeisung Leistung', 'power', 'measurement', 'W'),
    'energy_today': ('PV-Energie heute', 'energy', None, 'kWh'),
    'consumption_energy_today': ('Hausverbrauch heute', 'energy', None, 'kWh'),
    'grid_import_energy_today': ('Netzbezug heute', 'energy', None, 'kWh'),
    'grid_export_energy_today': ('Einspeisung heute', 'energy', None, 'kWh'),
    'self_consumption_energy_today': ('PV-Eigenverbrauch heute', 'energy', None, 'kWh'),
    'autarky_today': ('Autarkie heute', None, None, '%'),
    'self_consumption_ratio_today': ('Eigenverbrauchsquote heute', None, None, '%'),
    'energy_date': ('Datum der Tageswerte', 'date', None, None),
    'pv_energy_total': ('PV-Erzeugung gesamt', 'energy', 'total', 'kWh'),
    'grid_import_energy_total': ('Netzbezug gesamt', 'energy', 'total', 'kWh'),
    'grid_export_energy_total': ('Netzeinspeisung gesamt', 'energy', 'total', 'kWh'),
    'consumption_energy_total': ('Hausverbrauch gesamt', 'energy', 'total', 'kWh'),
    'self_consumption_energy_total': ('PV-Eigenverbrauch gesamt', 'energy', 'total', 'kWh'),
    'outside_temperature': ('Außentemperatur', 'temperature', 'measurement', '°C'),
    'site_status': ('Anlagenstatus', None, None, None),
    'last_update': ('SolarEdge Aktualisierung', None, None, None),
    'scraper_last_success': ('Letzter erfolgreicher Abruf', 'timestamp', None, None),
    'scraper_last_attempt': ('Letzter Abrufversuch', 'timestamp', None, None),
    'scraper_status': ('Abrufstatus', None, None, None),
    'scraper_response_time': ('Abrufdauer', 'duration', 'measurement', 's'),
    'energy_gap_count': ('Fehlende Energietage', None, None, None),
    'data_freshness': ('Datenzustand', 'enum', None, None),
    'scraper_poll_interval': ('Abrufintervall', 'duration', None, 's'),
    'scraper_stale_after': ('Warnschwelle Datenalter', 'duration', None, 's'),
    'history_import_status': ('Historienimport', 'enum', None, None),
    'history_last_success': ('Letzter Historienimport', 'timestamp', None, None),
}
DIAGNOSTIC = {k for k in SENSORS if k.startswith(('scraper_', 'history_'))} | {'energy_gap_count', 'data_freshness', 'energy_date'}
DAILY = {k for k in SENSORS if k.endswith('_today')}
FRESHNESS_OPTIONS = ['waiting', 'fresh', 'updating', 'retrying', 'stale', 'error',
                     'login_required', 'manual_login_required', 'energy_ledger_error',
                     'rate_limited', 'offline']


def broker_options(config):
    if config.mqtt_host:
        return config.mqtt_host, config.mqtt_port, config.mqtt_username, config.mqtt_password, config.mqtt_tls
    token = os.getenv('SUPERVISOR_TOKEN')
    if not token:
        raise ValueError('MQTT host missing; configure broker or use Supervisor MQTT service')
    request = Request('http://supervisor/services/mqtt', headers={'Authorization':'Bearer ' + token})
    # Supervisor lookup is local configuration, never a SolarEdge data source.
    with urlopen(request, timeout=10) as response:
        envelope = json.load(response)
    data = envelope['data']
    if envelope.get('result') != 'ok' or data.get('protocol', '3.1.1') != '3.1.1':
        raise ValueError('Supervisor MQTT service unavailable or unsupported')
    return data['host'], int(data['port']), data.get('username', ''), data.get('password', ''), bool(data.get('ssl', False))


class MqttPublisher:
    def __init__(self, config):
        self.config = config
        self.device_id = 'seweb_' + identity(config)
        self.base = 'solaredge_web/' + self.device_id
        self.client = None
        self.lock = threading.RLock()
        self.cache = {}
        self.present = set()
        self.last_success = 0.0
        self.solar_online = False
        self.started = False
        self.created_at = time.time()
        self.validity_cache = {}
        self.marked_unavailable = False

    @property
    def connected(self):
        return bool(self.client and self.client.is_connected())

    async def start(self):
        host, port, user, password, tls = await asyncio.to_thread(broker_options, self.config)
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.device_id, protocol=mqtt.MQTTv311)
        if user:
            client.username_pw_set(user, password)
        if tls:
            client.tls_set()
        client.will_set(self.base + '/connection', 'offline', qos=1, retain=True)
        client.reconnect_delay_set(min_delay=5, max_delay=300)
        client.on_connect = self.on_connect
        client.on_disconnect = self.on_disconnect
        self.client = client
        client.connect_async(host, port, keepalive=60)
        client.loop_start()
        self.started = True

    def config_payload(self, key):
        name, device_class, state_class, unit = SENSORS[key]
        diagnostic = key in DIAGNOSTIC
        payload = {
            'name':name, 'unique_id':self.device_id + '_' + key,
            'default_entity_id':'sensor.solaredge_' + key,
            'state_topic':self.base + '/state/' + key, 'qos':1,
            'availability':[
                {'topic':self.base + '/connection'},
                {'topic':self.base + ('/process' if diagnostic else '/availability')},
                {'topic':self.base + '/valid/' + key},
            ], 'availability_mode':'all',
            'device':{'identifiers':[self.device_id], 'name':'SolarEdge Web Scraper',
                      'manufacturer':'SolarEdge / Community', 'model':'Monitoring Web UI', 'sw_version':'0.3.1'},
            'origin':{'name':'SolarEdge Web Scraper','sw_version':'0.3.1',
                      'support_url':'https://github.com/dr8ecker/solaredge_web'},
        }
        if diagnostic:
            payload['entity_category'] = 'diagnostic'
        if device_class:
            payload['device_class'] = device_class
        if state_class:
            payload['state_class'] = state_class
        if unit:
            payload['unit_of_measurement'] = unit
        if key == 'data_freshness':
            payload['options'] = FRESHNESS_OPTIONS
        elif key == 'history_import_status':
            payload['options'] = ['waiting', 'ok', 'error', 'disabled', 'supervisor_required']
        return payload

    def publish(self, topic, payload):
        return self.client.publish(topic, payload, qos=1, retain=True)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            LOGGER.warning('MQTT broker rejected connection; check broker configuration')
            return
        with self.lock:
            self.validity_cache.clear()
            # Clear stale retained availability before reconnecting a new run.
            self.publish_availability()
            self.publish(self.base + '/connection', 'online')
            self.publish(self.base + '/process', 'online')
            if self.cache.get('scraper_status') == 'mqtt_disconnected':
                self.cache['scraper_status'] = 'connected'
            for key in SENSORS:
                payload = self.config_payload(key)
                self.publish(self.config.mqtt_discovery_prefix + '/sensor/' + self.device_id + '_' + key + '/config', json.dumps(payload, ensure_ascii=False))
            for key, value in self.cache.items():
                self.publish(self.base + '/state/' + key, self.encode(value))
            self.publish_validity()
            self.publish_availability()
        LOGGER.info('MQTT connected; Home Assistant discovery published')

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        with self.lock:
            if self.cache.get('scraper_status') == 'connected':
                self.cache['scraper_status'] = 'mqtt_disconnected'
        LOGGER.info('MQTT disconnected; automatic reconnect enabled')

    @staticmethod
    def encode(value):
        return json.dumps(value, allow_nan=False) if isinstance(value, (int, float)) else str(value)

    def publish_validity(self):
        day = datetime.now(ZoneInfo(self.config.site_timezone)).date().isoformat()
        for key in SENSORS:
            valid = key in self.present and (key not in DAILY or self.cache.get('energy_date') == day)
            value = 'online' if valid else 'offline'
            if self.validity_cache.get(key) != value:
                self.publish(self.base + '/valid/' + key, value)
                self.validity_cache[key] = value

    def freshness(self, now=None):
        now = time.time() if now is None else now
        status = self.cache.get('scraper_status', '')
        if status in {'login_required', 'manual_login_required', 'energy_ledger_error', 'rate_limited', 'offline'}:
            return status
        if now - (self.last_success or self.created_at) > self.config.health_max_age:
            return 'stale'
        if self.marked_unavailable:
            return 'error'
        if status == 'error':
            return 'retrying'
        if status == 'scraping':
            return 'updating'
        return 'fresh' if self.last_success else 'waiting'

    def publish_health(self):
        values = {'data_freshness': self.freshness(), 'scraper_poll_interval': self.config.poll_interval,
                  'scraper_stale_after': self.config.health_max_age}
        for key, value in values.items():
            changed = self.cache.get(key) != value
            self.cache[key] = value
            self.present.add(key)
            if changed and self.connected:
                self.publish(self.base + '/state/' + key, self.encode(value))

    def publish_availability(self):
        with self.lock:
            self.publish_health()
            self.publish_validity()
            fresh = self.solar_online and time.time() - self.last_success <= self.config.health_max_age
            self.publish(self.base + '/availability', 'online' if fresh else 'offline')

    def update(self, values, *, solar_success=False):
        with self.lock:
            if solar_success:
                # Omitted live fields are explicitly unavailable. Cached states
                # remain retained but cannot masquerade as current values.
                self.present.difference_update(set(SENSORS) - DIAGNOSTIC)
                self.last_success = time.time()
                self.solar_online = True
                self.marked_unavailable = False
            for key, value in values.items():
                if key in SENSORS and value is not None:
                    self.cache[key] = value
                    self.present.add(key)
                    if self.connected:
                        self.publish(self.base + '/state/' + key, self.encode(value))
            self.publish_health()
            if self.connected:
                self.publish_validity()
                self.publish_availability()

    def unavailable(self):
        with self.lock:
            self.solar_online = False
            self.marked_unavailable = True
            if self.connected:
                self.publish_availability()

    async def close(self):
        if self.client:
            if self.connected:
                self.publish(self.base + '/process', 'offline')
                self.publish(self.base + '/connection', 'offline')
                packet = self.publish(self.base + '/availability', 'offline')
                try:
                    await asyncio.to_thread(packet.wait_for_publish, 3)
                except Exception:
                    pass
            self.client.disconnect()
            await asyncio.to_thread(self.client.loop_stop)
        self.started = False
