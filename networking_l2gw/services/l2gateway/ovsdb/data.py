# Copyright (c) 2015 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from neutron.common import constants
from neutron import manager
from neutron.plugins.ml2.drivers.l2pop import rpc as l2pop_rpc

from networking_l2gw.db.l2gateway.ovsdb import lib as db
from networking_l2gw.services.l2gateway.common import constants as n_const
from networking_l2gw.services.l2gateway.common import topics
from networking_l2gw.services.l2gateway import plugin as l2gw_plugin

from oslo.config import cfg
from oslo import messaging
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class L2GatewayOVSDBCallbacks(object):
    """Implement the rpc call back functions from OVSDB."""

    target = messaging.Target(version='1.0')

    def __init__(self, plugin):
        super(L2GatewayOVSDBCallbacks, self).__init__()
        self.plugin = plugin

    def update_ovsdb_changes(self, context, ovsdb_data):
        """RPC to update the changes from OVSDB in the database."""
        self.ovsdb = OVSDBData(
            ovsdb_data.get(n_const.OVSDB_IDENTIFIER))
        self.ovsdb.update_ovsdb_changes(context, ovsdb_data)


class OVSDBData(object):
    """Process the data coming from OVSDB."""

    def __init__(self, ovsdb_identifier=None):
        self.ovsdb_identifier = ovsdb_identifier
        self._setup_entry_table()
        self.agent_rpc = l2gw_plugin.L2gatewayAgentApi(
            topics.L2GATEWAY_AGENT, cfg.CONF.host)

    def update_ovsdb_changes(self, context, ovsdb_data):
        """RPC to update the changes from OVSDB in the database."""

        for item, value in ovsdb_data.items():
            lookup = self.entry_table.get(item, None)
            if lookup:
                lookup(context, value)
        if ovsdb_data.get('new_remote_macs'):
            self._handle_l2pop(context, ovsdb_data.get('new_remote_macs'))

    def _setup_entry_table(self):
        self.entry_table = {'new_logical_switches':
                            self._process_new_logical_switches,
                            'new_physical_ports':
                            self._process_new_physical_ports,
                            'new_physical_switches':
                            self._process_new_physical_switches,
                            'new_physical_locators':
                            self._process_new_physical_locators,
                            'new_local_macs':
                            self._process_new_local_macs,
                            'new_remote_macs':
                            self._process_new_remote_macs,
                            'modified_physical_ports':
                            self._process_modified_physical_ports,
                            'deleted_logical_switches':
                            self._process_deleted_logical_switches,
                            'deleted_physical_ports':
                            self._process_deleted_physical_ports,
                            'deleted_physical_switches':
                            self._process_deleted_physical_switches,
                            'deleted_physical_locators':
                            self._process_deleted_physical_locators,
                            'deleted_local_macs':
                            self._process_deleted_local_macs,
                            'deleted_remote_macs':
                            self._process_deleted_remote_macs,
                            'modified_physical_switches':
                            self._process_modified_physical_switches,
                            }

        return

    def _process_new_logical_switches(self,
                                      context,
                                      new_logical_switches):
        for logical_switch in new_logical_switches:
            ls_dict = logical_switch
            ls_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            l_switch = db.get_logical_switch(context, ls_dict)
            if not l_switch:
                db.add_logical_switch(context, ls_dict)

    def _process_new_physical_switches(self,
                                       context,
                                       new_physical_switches):
        for physical_switch in new_physical_switches:
            ps_dict = physical_switch
            ps_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            if (ps_dict.get('tunnel_ip'))[0] == 'set':
                ps_dict['tunnel_ip'] = None
            p_switch = db.get_physical_switch(context, ps_dict)
            if not p_switch:
                db.add_physical_switch(context, ps_dict)

    def _process_new_physical_ports(self,
                                    context,
                                    new_physical_ports):
        for physical_port in new_physical_ports:
            pp_dict = physical_port
            pp_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            p_port = db.get_physical_port(context, pp_dict)
            if not p_port:
                db.add_physical_port(context, pp_dict)
            if pp_dict.get('vlan_bindings'):
                for vlan_binding in pp_dict.get('vlan_bindings'):
                    vlan_binding[
                        n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
                    vlan_binding['port_uuid'] = pp_dict.get('uuid')
                    v_binding = db.get_vlan_binding(context, vlan_binding)
                    if not v_binding:
                        db.add_vlan_binding(context, vlan_binding)

    def _process_new_physical_locators(self,
                                       context,
                                       new_physical_locators):
        for physical_locator in new_physical_locators:
            pl_dict = physical_locator
            pl_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            p_locator = db.get_physical_locator(context, pl_dict)
            if not p_locator:
                db.add_physical_locator(context, pl_dict)

    def _process_new_local_macs(self,
                                context,
                                new_local_macs):
        for local_mac in new_local_macs:
            lm_dict = local_mac
            lm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            lm_dict['logical_switch_uuid'] = local_mac.get('logical_switch_id')
            l_mac = db.get_ucast_mac_local(context, lm_dict)
            if not l_mac:
                db.add_ucast_mac_local(context, lm_dict)

    def _process_new_remote_macs(self,
                                 context,
                                 new_remote_macs):
        for remote_mac in new_remote_macs:
            rm_dict = remote_mac
            rm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            r_mac = db.get_ucast_mac_remote(context, rm_dict)
            if not r_mac:
                db.add_ucast_mac_remote(context, rm_dict)

    def _get_physical_switch_ips(self, context, mac):
        physical_switch_ips = set()
        record_dict = {n_const.OVSDB_IDENTIFIER: self.ovsdb_identifier}
        vlan_bindings = db.get_all_vlan_bindings_by_logical_switch(
            context, mac)
        for vlan_binding in vlan_bindings:
            record_dict['uuid'] = vlan_binding.get('port_uuid')
            physical_port = db.get_physical_port(context, record_dict)
            record_dict['uuid'] = physical_port.get('physical_switch_id')
            physical_switch = db.get_physical_switch(context, record_dict)
            physical_switch_ips.add(physical_switch.get('tunnel_ip'))
        return list(physical_switch_ips)

    def _handle_l2pop(self, context, new_remote_macs):
        for mac in new_remote_macs:
            agent_ips = self._get_physical_switch_ips(context, mac)
            for agent_ip in agent_ips:
                other_fdb_entries = self._get_fdb_entries(
                    context, agent_ip, mac.get('logical_switch_id'))
                self._trigger_l2pop_sync(context, other_fdb_entries)

    def _process_modified_physical_ports(self,
                                         context,
                                         modified_physical_ports):
        for physical_port in modified_physical_ports:
            pp_dict = physical_port
            pp_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            modified_port = db.get_physical_port(context, pp_dict)
            if modified_port:
                db.update_physical_ports_status(context, pp_dict)
                port_vlan_bindings = physical_port.get('vlan_bindings')
                vlan_bindings = db.get_all_vlan_bindings_by_physical_port(
                    context, pp_dict)
                for vlan_binding in vlan_bindings:
                    db.delete_vlan_binding(context, vlan_binding)
                for port_vlan_binding in port_vlan_bindings:
                    port_vlan_binding['port_uuid'] = pp_dict['uuid']
                    port_vlan_binding[
                        n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
                    db.add_vlan_binding(context, port_vlan_binding)
            else:
                db.add_physical_port(context, pp_dict)

    def _process_modified_physical_switches(self, context,
                                            modified_physical_switches):
        for physical_switch in modified_physical_switches:
            db.update_physical_switch_status(context, physical_switch)

    def _process_deleted_logical_switches(self,
                                          context,
                                          deleted_logical_switches):
        for logical_switch in deleted_logical_switches:
            ls_dict = logical_switch
            ls_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_logical_switch(context, ls_dict)

    def _process_deleted_physical_switches(self,
                                           context,
                                           deleted_physical_switches):
        for physical_switch in deleted_physical_switches:
            ps_dict = physical_switch
            ps_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_physical_switch(context, ps_dict)

    def _process_deleted_physical_ports(self,
                                        context,
                                        deleted_physical_ports):
        for physical_port in deleted_physical_ports:
            pp_dict = physical_port
            pp_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_physical_port(context, pp_dict)

    def _process_deleted_physical_locators(self,
                                           context,
                                           deleted_physical_locators):
        physical_switch_ips = []
        logical_switch_ids = self._get_logical_switch_ids(context)
        physical_switches = db.get_all_physical_switches_by_ovsdb_id(
            context, self.ovsdb_identifier)
        for physical_switch in physical_switches:
            physical_switch_ips.append(
                physical_switch.get('tunnel_ip'))
        tunneling_ip_dict = self._get_agent_ips(context)
        for physical_locator in deleted_physical_locators:
            pl_dict = physical_locator
            pl_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            agent_ip = physical_locator.get('dst_ip')
            if agent_ip in tunneling_ip_dict.keys():
                for logical_switch_id in logical_switch_ids:
                    for physical_switch_ip in physical_switch_ips:
                        other_fdb_entries = self._get_fdb_entries(
                            context, physical_switch_ip, logical_switch_id)
                        agent_host = tunneling_ip_dict.get(agent_ip)
                        self._trigger_l2pop_delete(
                            context, other_fdb_entries, agent_host)
            else:
                for logical_switch_id in logical_switch_ids:
                    other_fdb_entries = self._get_fdb_entries(
                        context, agent_ip, logical_switch_id)
                    self._trigger_l2pop_delete(
                        context, other_fdb_entries)
            db.delete_physical_locator(context, pl_dict)

    def _process_deleted_local_macs(self,
                                    context,
                                    deleted_local_macs):
        for local_mac in deleted_local_macs:
            lm_dict = local_mac
            lm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_ucast_mac_local(context, lm_dict)

    def _process_deleted_remote_macs(self,
                                     context,
                                     deleted_remote_macs):
        for remote_mac in deleted_remote_macs:
            rm_dict = remote_mac
            rm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_ucast_mac_remote(context, rm_dict)

    def _get_logical_switch_ids(self, context):
        logical_switch_ids = set()
        logical_switches = db.get_all_logical_switches_by_ovsdb_id(
            context, self.ovsdb_identifier)
        for logical_switch in logical_switches:
                logical_switch_ids.add(logical_switch.get('uuid'))
        return list(logical_switch_ids)

    def _get_agent_ips(self, context):
        agent_ip_dict = {}
        ml2plugin = manager.NeutronManager.get_plugin()
        agents = ml2plugin.get_agents(
            context, filters={'agent_type': [constants.AGENT_TYPE_OVS]})
        for agent in agents:
            conf_dict = agent.get('configurations')
            tunnel_ip = conf_dict.get('tunneling_ip')
            agent_ip_dict[tunnel_ip] = agent.get('host')
        return agent_ip_dict

    def _get_fdb_entries(self, context, agent_ip, logical_switch_uuid):
        ls_dict = {'uuid': logical_switch_uuid,
                   n_const.OVSDB_IDENTIFIER: self.ovsdb_identifier}
        logical_switch = db.get_logical_switch(context, ls_dict)
        network_id = logical_switch.get('name')
        segment_id = logical_switch.get('key')
        port_fdb_entries = constants.FLOODING_ENTRY
        other_fdb_entries = {network_id: {'segment_id': segment_id,
                                          'network_type': 'vxlan',
                                          'ports': {agent_ip:
                                                    [port_fdb_entries]
                                                    }}}
        return other_fdb_entries

    def _trigger_l2pop_sync(self, context, other_fdb_entries):
        """Sends L2pop ADD RPC message to the neutron L2 agent."""
        l2pop_rpc.L2populationAgentNotifyAPI(
            ).add_fdb_entries(context, other_fdb_entries)

    def _trigger_l2pop_delete(self, context, other_fdb_entries, host=None):
        """Sends L2pop DELETE RPC message to the neutron L2 agent."""
        l2pop_rpc.L2populationAgentNotifyAPI(
            ).remove_fdb_entries(context, other_fdb_entries, host)
