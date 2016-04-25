#
# Copyright (c) 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Comparing an application from appstack to its counterpart in the live environment.
"""

import logging
import pkg_resources

import datadiff
from requests.structures import CaseInsensitiveDict

from . import cf_api
from . import cf_cli

_log = logging.getLogger(__name__) # pylint: disable=invalid-name


def should_update(app):
    """Checks whether an application should be updated (or created from scratch) in the live
    Cloud Foundry environment.

    Args:
        app (`apployer.appstack.AppConfig`): An application.

    Returns:
        bool: True if the app should be pushed, False otherwise.
    """
    try:
        app_guid = cf_cli.get_app_guid(app.name)
    except cf_cli.CommandFailedError as ex:
        _log.debug(str(ex))
        _log.info("Failed to get GUID of app %s. Assuming it doesn't exist yet. "
                  "Will need to push it...", app.name)
        return True
    app_summary = cf_api.get_app_summary(app_guid)
    app_properties = app.app_properties

    appstack_version, live_env_version = _get_app_versions(app_properties, app_summary)
    if appstack_version > live_env_version:
        _log.info("Appstack's version of the app (%s) is higher than in the live env (%s). "
                  "Will update...", appstack_version, live_env_version)
        return True
    elif appstack_version < live_env_version:
        _log.info("Appstack's version of the app (%s) is lower than in the live env (%s). "
                  "Won't push, because that would downgrade the app...",
                  appstack_version, live_env_version)
        return False

    return _properties_differ(app_properties, app_summary)


def _get_app_versions(app_properties, app_summary):
    """
    Args:
        app_properties (dict): Application's properties from appstack.
        app_summary (dict): Application's properties from Cloud Foundry.

    Returns:
        (`pkg_resources.SetuptoolsVersion`, `pkg_resources.SetuptoolsVersion`): Tuple in form:
            (app_version_in_appstack, app_version_in_live_env).
            If version isn't found, then the lowest possible version will be returned.
    """
    appstack_version = app_properties.get('env', {}).get('VERSION', '')
    live_env_version = app_summary.get('environment_json', {}).get('VERSION', '')
    # empty version string will be parsed to the lowest possible version
    return (pkg_resources.parse_version(appstack_version),
            pkg_resources.parse_version(live_env_version))


def _properties_differ(app_properties, app_summary):
    """Compares application's properties from appstack to those taken from a live environment.

    Args:
        app_properties (dict): Application's properties from appstack.
        app_summary (dict): Application's properties from Cloud Foundry.

    Returns:
        bool: True if one of the properties present in `app_properties` is different in
            `app_summary`. False otherwise.
    """
    for key, value in app_properties.items():
        if key == 'env':
            if not _dict_is_part_of(app_summary['environment_json'], value):
                _log.info("Differences in application's env:\n%s",
                          datadiff.diff(app_summary['environment_json'], value,
                                        fromfile='live env', tofile='appstack'))
                return True
        elif key in ('disk_quota', 'memory'):
            # Values in the manifest will be strings and have suffix M, MB, G or GB,
            # while values in summary will be ints specifying the number of megabytes.
            megabytes_in_properties = _normalize_to_megabytes(value)
            if megabytes_in_properties != app_summary[key]:
                _log.info("Difference in application's %s field: %s (live env) vs. %s (appstack).",
                          key, app_summary[key], megabytes_in_properties)
                return True
        elif key == 'services':
            summary_services = [service['name'] for service in app_summary[key]]
            if not set(value).issubset(set(summary_services)):
                _log.info("Difference in application's services: \n%s",
                          datadiff.diff(app_summary[key], value,
                                        fromfile='live env', tofile='appstack'))
                return True
        elif key == 'host':
            summary_hosts = [route['host'] for route in app_summary['routes']]
            if value not in summary_hosts:
                _log.info("Application's hosts in live env don't contain %s.", value)
                return True
        else:
            if value != app_summary[key]:
                _log.info("Difference in application's %s field: %s (live env) vs. %s (appstack).",
                          key, app_summary[key], value)
                return True
    return False


def _dict_is_part_of(dict_a, dict_b):
    """
    Checks whether dict_b is a part of dict_a.
    That is if dict_b is dict_a, just with some (or none) keys removed.

    Args:
        dict_a (dict):
        dict_b (dict):

    Return:
        bool: True if dict_a contains dict_b.
    """
    dict_a, dict_b = CaseInsensitiveDict(dict_a), CaseInsensitiveDict(dict_b)
    for key, value in dict_b.items():
        if key not in dict_a or dict_a[key] != value:
            return False
    return True


def _normalize_to_megabytes(value):
    """
    Args:
        value (str): A string with a number and a size suffix, like 2GB or 300M.

    Returns:
        int: Number of megabytes represented by the `value`.
    """
    if value.endswith('M'):
        return int(value[:-1])
    elif value.endswith('MB'):
        return int(value[:-2])
    elif value.endswith('G'):
        return int(value[:-1]) * 1024
    elif value.endswith('GB'):
        return int(value[:-2]) * 1024
