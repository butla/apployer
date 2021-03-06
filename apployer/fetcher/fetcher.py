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
High level interface for filling the expanded appstack file with configuration values taken from
live TAP environment.
"""

import logging
import os
import pprint

import jinja2
import yaml

from .cdh_utilities import CdhConfExtractor
from .conf_finalizer import deduce_final_configuration
from .bastion_utilities import CFConfExtractor

DEPLOY_CONF_FILE = 'templates/template_variables.yml'
DEFAULT_FILLED_APPSTACK_PATH = 'filled_expanded_appstack.yml'
DEFAULT_FETCHER_CONF = 'fetcher_config.yml'

_log = logging.getLogger(__name__) # pylint: disable=invalid-name


def fill_appstack(expanded_appstack_file, fetcher_config_path):
    """Fills expanded appstack with configuration taken from a live environment.
    Args:
        expanded_appstack_file:
        fetcher_config_path:

    Returns:
        str: Filled expanded appstack's path.
    """
    if not fetcher_config_path:
        fetcher_config_path = DEFAULT_FETCHER_CONF
    fetcher_config = _get_fetcher_config(fetcher_config_path)
    env_conf_values = _get_environment_config(fetcher_config)
    filled_config = _get_full_deployment_config(env_conf_values)
    _fill_appstack(expanded_appstack_file, filled_config, DEFAULT_FILLED_APPSTACK_PATH)
    return DEFAULT_FILLED_APPSTACK_PATH


def _get_fetcher_config(fetcher_config_path):
    _log.debug('Using configuration file: %s', fetcher_config_path)
    with open(fetcher_config_path) as fetcher_config_file:
        fetcher_config = yaml.load(fetcher_config_file)
    return _fill_config_defaults(fetcher_config)


def _fill_config_defaults(fetcher_config):
    config_with_defaults = fetcher_config.copy()
    is_openstack = config_with_defaults['openstack_env']
    cdh_launcher_conf = config_with_defaults['machines']['cdh-launcher']

    if not cdh_launcher_conf['username']:
        if is_openstack:
            cdh_launcher_conf['username'] = 'centos'
        else:
            cdh_launcher_conf['username'] = 'ec2-user'
    return config_with_defaults


def _get_environment_config(fetcher_config):
    _log.info("Extracting configuration values from CDH...")
    with CdhConfExtractor(fetcher_config) as cdh_extractor:
        cdh_conf = cdh_extractor.get_all_deployments_conf()

    _log.info("Extracting configuration values from bastion...")
    with CFConfExtractor(fetcher_config) as cf_extractor:
        env_conf = cf_extractor.get_environment_settings()

    fetched_config = dict(cdh_conf.items() + env_conf.items())
    _log.debug('Config values fetched from environment:\n%s', pprint.pformat(fetched_config))
    return fetched_config


def _get_full_deployment_config(env_conf_values):
    _log.debug("Loading deployment configuration file: %s", DEPLOY_CONF_FILE)
    with open(DEPLOY_CONF_FILE, 'r') as variables_file:
        deployment_variables = yaml.load(variables_file)

    for key, value in env_conf_values.iteritems():
        if not deployment_variables.get(key):
            deployment_variables[key] = value
    deployment_variables_final = deduce_final_configuration(deployment_variables)
    return deployment_variables_final


def _fill_appstack(expanded_appstack_file, filled_config, filled_appstack_path):
    """
    Args:
        expanded_appstack_file (str):
        filled_config (dict):
        filled_appstack_path (str): Where to save the filled appstack file.
    """
    _log.info('Filling expanded appstack with configuration...')
    _log.debug('Expanded appstack file: %s', expanded_appstack_file)

    with open(expanded_appstack_file, 'r') as appstack_file:
        appstack_str = appstack_file.read()
    appstack_template = jinja2.Environment().from_string(appstack_str)
    full_appstack_str = appstack_template.render(filled_config)

    with open(filled_appstack_path, 'w') as appstack_file:
        appstack_file.write(full_appstack_str)
    _log.info('Filled expanded appstack file: %s', os.path.realpath(filled_appstack_path))
