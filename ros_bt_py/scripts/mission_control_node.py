#!/usr/bin/env python3
"""
ROS Node running the MissionControl class.
"""

# pylint: disable=import-error, no-name-in-module

import rospy
import std_msgs
from ros_bt_py_msgs.srv import GetCapabilityInterfaces

from ros_bt_py.capability import capability_node_class_from_capability_interface_callback
from ros_bt_py.mission_control import MissionControl

if __name__ == '__main__':
    local_repository_prefix = rospy.get_param(
        "~local_repository_prefix",
        default="/capability_repository_node"
    )

    local_mc_prefix = f"{rospy.get_namespace()}/mission_control"

    get_capability_interface_service = rospy.ServiceProxy(
        name=f"{rospy.get_namespace()}/capability_repository/capabilities/interfaces/get",
        service_class=GetCapabilityInterfaces,
        persistent=True,
    )

    capability_interface_subscription = rospy.Subscriber(
        name=f"{rospy.get_namespace()}/capability_repository/capabilities/interfaces",
        data_class=std_msgs.msg.Time,
        callback=capability_node_class_from_capability_interface_callback,
        callback_args=(local_mc_prefix, get_capability_interface_service,),
    )

    rospy.init_node('mission_control')

    MISSION_CONTROL = MissionControl()
    rospy.spin()
