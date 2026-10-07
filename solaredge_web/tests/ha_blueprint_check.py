# Copyright (c) 2026 8ecker.de
"""Run inside the HA test image; validates templates without sending a message."""
import asyncio

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA, PLATFORM_SCHEMA
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.components.mobile_app.device_action import ACTION_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.util.yaml import load_yaml, objects


async def main():
    hass = HomeAssistant('/tmp/seweb-blueprint-validation')
    raw = load_yaml('/config/solaredge-outage.yaml')
    Blueprint(raw, expected_domain='automation', schema=AUTOMATION_BLUEPRINT_SCHEMA)
    values = {key: info.get('default') for key, info in raw['blueprint']['input'].items()}
    values['notify_device'] = '0123456789abcdef0123456789abcdef'

    def substitute(value):
        if isinstance(value, objects.Input):
            return values[value.name]
        if isinstance(value, dict):
            return {key:substitute(item) for key,item in value.items()}
        if isinstance(value, list):
            return [substitute(item) for item in value]
        return value

    config = substitute({key:value for key,value in raw.items() if key != 'blueprint'})
    PLATFORM_SCHEMA(config)
    ACTION_SCHEMA(config['actions'][0])
    ACTION_SCHEMA(config['actions'][2]['then'][0])
    trigger = Template(config['triggers'][0]['value_template'], hass)
    recovery = Template(config['actions'][1]['wait_template'], hass)
    for state, history, warning, recovered in [
        ('fresh','ok',False,True), ('updating','ok',False,False), ('retrying','ok',False,False),
        ('stale','ok',True,False), ('error','ok',True,False), ('manual_login_required','ok',True,False),
        ('terms_confirmation_required','ok',True,False),
        ('unavailable','ok',True,False), ('fresh','error',True,False), ('fresh','disabled',False,True),
        ('fresh','supervisor_required',True,False),
    ]:
        hass.states.async_set(values['freshness_entity'], state)
        hass.states.async_set(values['history_entity'], history)
        assert trigger.async_render(values) == warning, (state, history)
        assert recovery.async_render(values) == recovered, (state, history)
    print('Blueprint and device actions validated; warning/recovery templates passed 11 scenarios. No notifications sent.')


asyncio.run(main())
