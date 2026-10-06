# Copyright (c) 2026 8ecker.de
"""Allowlisted failure signals; never serialize browser exception messages."""

import platform
import re
from pathlib import Path

from .parser import ParseError
from .selectors import SELECTORS

VALIDATION_REASONS = {
    'Today did not select a single calendar day': 'today_not_single_day',
    'Unrecognized UI date format; run discovery': 'date_format_unrecognized',
    'Historical period did not match requested day': 'historical_date_mismatch',
    'Refusing overlapping or wrong energy period': 'energy_date_mismatch',
    'Energy cards and production KPI disagree; page still loading': 'production_kpi_mismatch',
    'Date changed during scrape': 'date_changed_during_scrape',
    'SolarEdge Today differs from site_timezone; no energy published': 'site_timezone_date_mismatch',
    'Day changed during scrape; retry before updating counters': 'day_changed_during_scrape',
}

NETWORK_ERRORS = {
    'ERR_NAME_NOT_RESOLVED', 'ERR_CONNECTION_REFUSED', 'ERR_CONNECTION_RESET',
    'ERR_CONNECTION_CLOSED', 'ERR_CONNECTION_TIMED_OUT', 'ERR_TIMED_OUT',
    'ERR_INTERNET_DISCONNECTED', 'ERR_NETWORK_CHANGED', 'ERR_ADDRESS_UNREACHABLE',
    'ERR_PROXY_CONNECTION_FAILED', 'ERR_TUNNEL_CONNECTION_FAILED',
    'ERR_CERT_AUTHORITY_INVALID', 'ERR_CERT_DATE_INVALID', 'ERR_CERT_COMMON_NAME_INVALID',
    'ERR_SSL_PROTOCOL_ERROR', 'ERR_ABORTED', 'ERR_FAILED', 'ERR_BLOCKED_BY_CLIENT',
    'ERR_TOO_MANY_REDIRECTS', 'ERR_HTTP_RESPONSE_CODE_FAILURE',
}


def failure_details(error):
    # Inspect internally, emit only fixed categories/codes. URLs, call logs,
    # inputs and cookie/header content from Playwright never leave this function.
    message = str(error)
    name = type(error).__name__
    kind = 'unknown'
    if 'Page crashed' in message or 'page has crashed' in message.lower():
        kind = 'page_crashed'
    elif name == 'TargetClosedError' or 'has been closed' in message:
        kind = 'target_closed'
    elif name in {'TimeoutError', 'TimeoutException'}:
        kind = 'timeout'
    elif re.search(r'Permission denied|Operation not permitted|EACCES|EPERM', message, re.I):
        kind = 'permission_denied'
    elif 'net::' in message:
        kind = 'network'
    elif 'interrupted by another navigation' in message:
        kind = 'navigation_interrupted'
    found = re.search(r'net::(ERR_[A-Z_]+)', message)
    code = found.group(1) if found and found.group(1) in NETWORK_ERRORS else None
    if code == 'ERR_ABORTED':
        kind = 'navigation_interrupted'
    result = {'error_type':name if name in {'Error', 'TimeoutError', 'TargetClosedError', 'RuntimeError', 'ValueError', 'ParseError', 'OSError'} else 'OtherError',
              'kind':kind, 'network_code':code}
    if isinstance(error, ValueError):
        result.update(kind='validation', reason=VALIDATION_REASONS.get(message, 'unknown_validation'))
        if isinstance(error, ParseError):
            result['reason'] = error.reason if error.reason in ParseError.REASONS.values() else 'unknown_validation'
            if error.field in ParseError.FIELDS:
                result['field'] = error.field
            missing = sorted(set(error.missing_fields) & ParseError.FIELDS)
            if missing:
                result['missing_fields'] = missing
            if error.label_count is not None:
                result['distribution_label_count'] = error.label_count
                result['unrecognized_tooltip_count'] = error.unrecognized_tooltip_count
        else:
            for field in SELECTORS:
                if message == f'Selector missing or ambiguous: {field}; run mode=discovery':
                    result.update(reason='selector_missing_or_ambiguous', field=field)
                    break
    return result


def runtime_details():
    result = {'architecture':platform.machine(), 'memory_limit_mb':None, 'oom_kills':None}
    try:
        limit = Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if limit.isdecimal():
            result['memory_limit_mb'] = int(limit)//1024//1024
        events = dict(line.split() for line in Path('/sys/fs/cgroup/memory.events').read_text().splitlines())
        result['oom_kills'] = int(events['oom_kill'])
    except (OSError, ValueError, KeyError):
        pass
    return result
