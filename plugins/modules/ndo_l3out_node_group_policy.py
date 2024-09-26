#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2024, Sabari Jaganathan (@sajagana) <sajagana@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {"metadata_version": "1.1", "status": ["preview"], "supported_by": "community"}

DOCUMENTATION = r"""
---
module: ndo_l3out_node_group_policy
short_description: Manage VLAN Pools on Cisco Nexus Dashboard Orchestrator (NDO).
description:
- Manage VLAN Pools on Cisco Nexus Dashboard Orchestrator (NDO).
- This module is only supported on ND v3.1 (NDO v4.3) and later.
author:
- Sabari Jaganathan (@sajagana)
options:
  template:
    description:
    - The name of the template.
    - The template must be a fabric policy template.
    type: str
    required: true
  vlan_pool:
    description:
    - The name of the VLAN Pool.
    type: str
    aliases: [ name ]
  vlan_pool_uuid:
    description:
    - The uuid of the VLAN Pool.
    - This parameter is required when the O(vlan_pool) needs to be updated.
    type: str
    aliases: [ uuid ]
  description:
    description:
    - The description of the VLAN Pool.
    type: str
  vlan_ranges:
    description:
    - A list of vlan ranges attached to the VLAN Pool.
    - The list of configured vlan ranges must contain at least one entry.
    - When the list of vlan ranges is null the update will not change existing entry configuration.
    type: list
    elements: dict
    suboptions:
      from_vlan:
        description:
        - The start of the VLAN range.
        type: int
        required: true
        aliases: [ from ]
      to_vlan:
        description:
        - The end of the VLAN range.
        type: int
        required: true
        aliases: [ to ]
  state:
    description:
    - Use C(absent) for removing.
    - Use C(query) for listing an object or multiple objects.
    - Use C(present) for creating or updating.
    type: str
    choices: [ absent, query, present ]
    default: query
extends_documentation_fragment: cisco.mso.modules
"""

EXAMPLES = r"""
- name: Create a new vlan pool
  cisco.mso.ndo_l3out_node_group_policy:
    host: mso_host
    username: admin
    password: SomeSecretPassword
    template: ansible_tenant_template
    vlan_pool: ansible_test_vlan_pool
    vlan_ranges:
      - from_vlan: 100
        to_vlan: 200
      - from_vlan: 300
        to_vlan: 400
    state: present

- name: Query a vlan pool with template_name
  cisco.mso.ndo_l3out_node_group_policy:
    host: mso_host
    username: admin
    password: SomeSecretPassword
    template: ansible_tenant_template
    vlan_pool: ansible_test_vlan_pool
    state: query
  register: query_one

- name: Query all vlan pools in the template
  cisco.mso.ndo_l3out_node_group_policy:
    host: mso_host
    username: admin
    password: SomeSecretPassword
    template: ansible_tenant_template
    state: query
  register: query_all

- name: Delete a vlan pool
  cisco.mso.ndo_l3out_node_group_policy:
    host: mso_host
    username: admin
    password: SomeSecretPassword
    template: ansible_tenant_template
    vlan_pool: ansible_test_vlan_pool
    state: absent
"""

RETURN = r"""
"""


import copy
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.cisco.mso.plugins.module_utils.mso import MSOModule, mso_argument_spec
from ansible_collections.cisco.mso.plugins.module_utils.template import MSOTemplate, KVPair
from ansible_collections.cisco.mso.plugins.module_utils.constants import TARGET_DSCP_MAP, ORIGINATE_DEFAULT_ROUTE, L3OUT_ROUTING_PROTOCOLS
from ansible_collections.cisco.mso.plugins.module_utils.utils import generate_api_endpoint


def main():
    argument_spec = mso_argument_spec()
    argument_spec.update(
        template=dict(type="str", required=True),  # L3Out template name
        l3out=dict(type="str", required=True),  # L3Out name
        name=dict(type="str"),  # node group policy name
        description=dict(type="str"),
        node_routing_policy=dict(type="str"),
        bfd_multi_hop_authentication=dict(type="str", aliases=["enabled", "disabled"]),
        bfd_multi_hop_key_id=dict(type="int"),
        bfd_multi_hop_key=dict(type="str"),
        target_dscp=dict(type="str", choices=list(TARGET_DSCP_MAP)),
        state=dict(type="str", default="query", choices=["absent", "query", "present"]),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ["state", "absent", ["name"]],
            ["state", "present", ["name"]],
            ["bfd_multi_hop_authentication", "enabled", ["bfd_multi_hop_key_id", "bfd_multi_hop_key"]],
        ],
    )

    mso = MSOModule(module)

    template = module.params.get("template")
    l3out = module.params.get("l3out")
    name = module.params.get("name")
    description = module.params.get("description")
    node_routing_policy = module.params.get("node_routing_policy")
    bfd_multi_hop_authentication = module.params.get("bfd_multi_hop_authentication")
    bfd_multi_hop_key_id = module.params.get("bfd_multi_hop_key_id")
    bfd_multi_hop_key = module.params.get("bfd_multi_hop_key")
    target_dscp = TARGET_DSCP_MAP.get(module.params.get("target_dscp"))
    state = module.params.get("state")

    l3out_template_object = MSOTemplate(mso, "l3out", template)
    l3out_template_object.validate_template("l3out")

    tenant_id = l3out_template_object.template_summary.get("tenantId")
    tenant_name = l3out_template_object.template_summary.get("tenantName")

    l3outs = l3out_template_object.template.get("l3outTemplate", {}).get("l3outs", [])

    l3out_template_object.set_l3out(name=l3out, fail_module=True)
    node_group_policy_path = "/l3outTemplate/l3outs/{0}/nodeGroups/".format(l3out_template_object.l3out.index)

    l3out_node_groups = l3out_template_object.l3out.details.get("nodeGroups", [])

    if state in ["query", "absent"] and l3out_node_groups == []:
        mso.exit_json()
    elif state == "query" and not name:
        mso.existing = l3out_node_groups
    elif l3out_node_groups and name:
        l3out_template_object.set_l3out_node_group(name)

        if l3out_template_object.l3out_node_group:
            mso.existing = copy.deepcopy(l3out_template_object.l3out_node_group.details)
            mso.previous = copy.deepcopy(l3out_template_object.l3out_node_group.details)

    ops = []

    if state == "present":
        node_routing_policy_object = None
        if node_routing_policy:
            l3out_node_policy_group_objects = mso.query_objs(
                generate_api_endpoint("templates/objects", **{"type": "l3OutNodePolGroup", "tenant-id": tenant_id, "include-common": "true"})
            )
            node_routing_policy_object = l3out_template_object.get_object_by_key_value_pairs(
                "L3Out Node Routing Policy", l3out_node_policy_group_objects, [KVPair("name", node_routing_policy)], True
            )

        # /mso/api/v1/templates/objects?type=l3OutNodePolGroup&tenant-id=66a11c7795400f37592efd10&include-common=True
        # https://173.36.219.35/mso/api/v1/templates/objects?type=l3OutNodePolGroup&tenant-id=668f345495400f37592e2a44&include-common=true
        if not mso.existing:
            # Sample Payload
            # {
            #     "name": "NodeGroupPolicy",
            #     "description": "Test Description",
            #     "nodeRoutingPolicyRef": "445fffaf-ec92-4973-954b-05fb6fc2576b",
            #     "bfdMultiHop": {
            #         "authEnabled": true,
            #         "keyID": 12,
            #         "key": {
            #             "value": "123"
            #         }
            #     },
            #     "targetDscp": "cs2"
            # }

            payload = dict(name=name)
            if description:
                payload["description"] = description
            if node_routing_policy and node_routing_policy_object:
                payload["nodeRoutingPolicyRef"] = node_routing_policy_object.details.get("uuid")
            if bfd_multi_hop_authentication == "enabled":
                payload["bfdMultiHop"] = dict(authEnabled=True, keyID=bfd_multi_hop_key_id, key=dict(value=bfd_multi_hop_key))

            if target_dscp:
                payload["targetDscp"] = target_dscp

            mso.sanitize(payload)
            ops.append(dict(op="add", path="{0}{1}".format(node_group_policy_path, "-"), value=payload))

        elif mso.existing:
            proposed_payload = copy.deepcopy(mso.existing)

            node_group_policy_attrs_path = "/l3outTemplate/l3outs/{0}/nodeGroups/{1}/".format(
                l3out_template_object.l3out.index, l3out_template_object.l3out_node_group.index
            )

            if description is not None and mso.existing.get("description") != description:
                ops.append(dict(op="replace", path=node_group_policy_attrs_path + "description", value=description))
                proposed_payload["description"] = description

            if node_routing_policy_object and mso.existing.get("nodeRoutingPolicyRef") != node_routing_policy_object.details.get("uuid"):
                ops.append(
                    dict(op="replace", path=node_group_policy_attrs_path + "nodeRoutingPolicyRef", value=node_routing_policy_object.details.get("uuid"))
                )
                proposed_payload["nodeRoutingPolicyRef"] = node_routing_policy_object.details.get("uuid")

            if bfd_multi_hop_authentication == "enabled":
                if not mso.existing.get("bfdMultiHop"):
                    proposed_payload["bfdMultiHop"] = dict()
                    ops.append(dict(op="replace", path=node_group_policy_attrs_path + "bfdMultiHop", value=dict()))

                if bfd_multi_hop_key_id and mso.existing.get("bfdMultiHop", {}).get("keyID") != bfd_multi_hop_key_id:
                    ops.append(dict(op="replace", path=node_group_policy_attrs_path + "bfdMultiHop/keyID", value=bfd_multi_hop_key_id))
                    proposed_payload["bfdMultiHop"]["keyID"] = bfd_multi_hop_key_id

                if bfd_multi_hop_key is not None:
                    # if bfd_multi_hop_key and mso.existing.get("bfdMultiHop", {}).get("value") != bfd_multi_hop_key:
                    ops.append(dict(op="replace", path=node_group_policy_attrs_path + "bfdMultiHop/value", value=bfd_multi_hop_key))
                    proposed_payload["bfdMultiHop"]["value"] = bfd_multi_hop_key

            elif bfd_multi_hop_authentication == "disabled":
                proposed_payload.pop("bfdMultiHop", None)
                ops.append(dict(op="remove", path=node_group_policy_attrs_path + "bfdMultiHop"))

            if target_dscp is not None and mso.existing.get("targetDscp") != target_dscp:
                ops.append(dict(op="replace", path=node_group_policy_attrs_path + "targetDscp", value=target_dscp))
                proposed_payload["targetDscp"] = target_dscp

            mso.sanitize(proposed_payload, collate=True)

        mso.existing = mso.proposed

    elif state == "absent":
        if mso.existing:
            # ops.append(dict(op="remove", path="/l3outTemplate/l3outs/{0}".format(match.index)))
            ops.append(
                dict(
                    op="remove",
                    path="/l3outTemplate/l3outs/{0}/nodeGroups/{1}".format(l3out_template_object.l3out.index, l3out_template_object.l3out_node_group.index),
                )
            )

        mso.existing = {}

    if not module.check_mode and ops:
        l3out_template_path = "{0}/{1}".format(l3out_template_object.templates_path, l3out_template_object.template_id)
        response = mso.request(l3out_template_path, method="PATCH", data=ops)

        l3out_template_object = MSOTemplate(mso, "l3out", template)
        l3out_template_object.validate_template("l3out")

        # tenant_id = l3out_template_object.template_summary.get("tenantId")
        # tenant_name = l3out_template_object.template_summary.get("tenantName")

        l3outs = l3out_template_object.template.get("l3outTemplate", {}).get("l3outs", [])

        l3out_template_object.set_l3out(name=l3out, fail_module=True)
        # node_group_policy_path = "/l3outTemplate/l3outs/{0}/nodeGroups/".format(l3out_template_object.l3out.index)

        # l3out_node_groups = l3out_template_object.l3out.details.get("nodeGroups", [])

        l3out_template_object.set_l3out_node_group(name)

        mso.existing = l3out_template_object.l3out_node_group

    mso.exit_json()


if __name__ == "__main__":
    main()


# [
#     {
#         "op": "add",
#         "path": "/l3outTemplate/l3outs/4/nodeGroups/-",
#         "value": {
#             "name": "NodeGroupPolicy",
#             "description": "Test Description",
#             "nodeRoutingPolicyRef": "445fffaf-ec92-4973-954b-05fb6fc2576b",
#             "bfdMultiHop": {
#                 "authEnabled": true,
#                 "keyID": 12,
#                 "key": {
#                     "value": "123"
#                 }
#             },
#             "targetDscp": "cs2"
#         }
#     }
# ]


# name
# description
# Node Routing Policy

# BFD Multi Hop [enabled, disabled]

# BFD Multi Hop: enabled
#   BFD Multi Hop Authentication [enabled, disabled]
#   BFD Multi Hop Authentication: enabled
#     Key ID
#     Key


# Final Attrs:

# name
# description
# node_routing_policy
# bfd_multi_hop_authentication - (enabled, disabled)
# bfd_multi_hop_key_id
# bfd_multi_hop_key
# target_dscp


# "anp":                       ObjectTypeAnp,
# "epg":                       ObjectTypeEpg,
# "bd":                        ObjectTypeBd,
# "vrf":                       ObjectTypeVrf,
# "filter":                    ObjectTypeFilter,
# "contract":                  ObjectTypeContract,
# "externalEpg":               ObjectTypeExternalEpg,
# "intersiteL3out":            ObjectTypeIntersiteL3out,
# "serviceGraph":              ObjectTypeServiceGraph,
# "serviceNode":               ObjectTypeServiceNode,
# "network":                   ObjectTypeNetwork,
# "dhcpRelay":                 ObjectTypeDhcpRelay,
# "dhcpOption":                ObjectTypeDhcpOption,
# "qos":                       ObjectTypeQos,
# "igmpInterface":             ObjectTypeIgmpInterface,
# "igmpSnoop":                 ObjectTypeIgmpSnoop,
# "mldSnoop":                  ObjectTypeMldSnoop,
# "routeMap":                  ObjectTypeRouteMap,
# "mcastRouteMap":             ObjectTypeMcastRouteMap,
# "vlanPool":                  ObjectTypeVlanPool,
# "domain":                    ObjectTypeDomain,
# "l3Domain":                  ObjectTypeL3Domain,
# "interfacePolicyGroup":      ObjectTypeInterfacePolicyGroup,
# "interfaceProfile":          ObjectTypeInterfaceProfile,
# "portChannel":               ObjectTypePortChannel,
# "virtualPortChannel":        ObjectTypeVirtualPortChannel,
# "ntp":                       ObjectTypeNtp,
# "podPolicyGroup":            ObjectTypePodPolicyGroup,
# "podProfile":                ObjectTypePodProfile,
# "accessMACsec":              ObjectTypeAccessMACsec,
# "syncEth":                   ObjectTypeSyncEth,
# "macsec":                    ObjectTypeMacsec,
# "qosMpls":                   ObjectTypeQosMpls,
# "qosClass":                  ObjectTypeQosClass,
# "qosDscpTranslation":        ObjectTypeQosDscpTranslation,
# "ptpProfile":                ObjectTypePtpProfile,
# "ptpPolicy":                 ObjectTypePtpPolicy,
# "nodePolicyGroup":           ObjectTypeNodePolicyGroup,
# "nodeProfile":               ObjectTypeNodeProfile,
# "spanSession":               ObjectTypeSpanSession,
# "mcpGlobalPolicy":           ObjectTypeMcpGlobalPolicy,
# "fexDevice":                 ObjectTypeFexDevice,
# "l3out":                     ObjectTypeL3out,
# "l3OutNodePolGroup":         ObjectTypeL3OutNodePolGroup,
# "l3OutIntfPolGroup":         ObjectTypeL3OutIntfPolGroup,
# "ipslaTrackList":            ObjectTypeIpslaTrackList,
# "ipslaMonitoringPolicy":     ObjectTypeIpslaMonitoringPolicy,
# "bgpPeerPrefixPol":          ObjectTypeBgpPeerPrefixPol,
# "srl3out":                   ObjectTypeSrl3out,
# "allL3out":                  ObjectTypeAllL3out,
# "serviceDevice":             ObjectTypeServiceDevice,
# "backupPolicy":              ObjectTypeBackupPolicy,
# "redirectDestPolicy":        ObjectTypeRedirectDestPolicy,
# "redirectHealthGroupPolicy": ObjectTypeRedirectHealthGroupPolicy,
# "redirectPolicy":            ObjectTypeRedirectPolicy,
# "l3OutSource":               ObjectTypeL3OutSource,
# "srL3OutSource":             ObjectTypeSrL3OutSource,
# "svcEpgPolicy":              ObjectTypeSvcEpgPolicy,
