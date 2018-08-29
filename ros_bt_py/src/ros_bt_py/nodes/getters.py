import rospy

from ros_bt_py_msgs.msg import Node as NodeMsg

from ros_bt_py.node import Decorator, define_bt_node
from ros_bt_py.node_config import NodeConfig, OptionRef


@define_bt_node(NodeConfig(
    options={'list_type': type,
             'index': int,
             'succeed_on_stale_data': bool},
    inputs={'list': list},
    outputs={'item': OptionRef('list_type')},
    max_children=1))
class GetListItem(Decorator):
    """Extracts the item at the given `index` from `list`

    The option parameter `succeed_on_stale_data` determines whether
    the node returns SUCCEEDED or RUNNING if `list` hasn't been
    updated since the last tick.

    """
    def _do_setup(self):
        for child in self.children:
            child.setup()
            # We have a child, so set list to an empty list. We're avoiding an
            # error this way because we know what we're doing, don't use this
            # gratuitously!
            self.inputs['list'] = []
        return NodeMsg.IDLE

    def _do_tick(self):
        # Tick child (if any) so it can produce its output before we process it
        for child in self.children:
            child.tick()

        if self.inputs.is_updated('list'):
            try:
                self.outputs['item'] = self.inputs['list'][self.options['index']]
                return NodeMsg.SUCCEEDED
            except IndexError:
                self.logerr('List index %d out of bound for list %s'
                            % (self.options['index'], self.inputs['list']))
                return NodeMsg.FAILED
        else:
            if self.options['succeed_on_stale_data']:
                return NodeMsg.SUCCEEDED
            else:
                self.loginfo('No new data since last tick!')
                return NodeMsg.RUNNING

    def _do_shutdown(self):
        pass

    def _do_reset(self):
        self.outputs['item'] = None
        self.outputs.reset_updated()
        self.inputs['list'] = None
        self._do_setup()
        self.inputs.reset_updated()
        return NodeMsg.IDLE

    def _do_untick(self):
        return NodeMsg.IDLE


@define_bt_node(NodeConfig(
    options={'value_type': type,
             'key': str,
             'succeed_on_stale_data': bool},
    inputs={'dict': dict},
    outputs={'value': OptionRef('value_type')},
    max_children=1))
class GetDictItem(Decorator):
    def _do_setup(self):
        for child in self.children:
            child.setup()
            # We have a child, so set dict to an empty dict. We're avoiding an
            # error this way because we know what we're doing, don't use this
            # gratuitously!
            self.inputs['dict'] = {}
        return NodeMsg.IDLE

    def _do_tick(self):
        # Tick child (if any) so it can produce its output before we process it
        for child in self.children:
            child.tick()

        if self.inputs.is_updated('dict'):
            try:
                self.outputs['value'] = self.inputs['dict'][self.options['key']]
                return NodeMsg.SUCCEEDED
            except KeyError:
                self.logerr('Key %s is not in dict %s'
                            % (self.options['key'], str(self.inputs['dict'])))
                return NodeMsg.FAILED
        else:
            if self.options['succeed_on_stale_data']:
                return NodeMsg.SUCCEEDED
            else:
                self.loginfo('No new data since last tick!')
                return NodeMsg.RUNNING

    def _do_shutdown(self):
        pass

    def _do_reset(self):
        self.outputs['value'] = None
        self.outputs.reset_updated()
        self.inputs['dict'] = None
        self._do_setup()
        self.inputs.reset_updated()
        return NodeMsg.IDLE

    def _do_untick(self):
        return NodeMsg.IDLE


@define_bt_node(NodeConfig(
    options={'attr_type': type,
             'attr_name': str,
             'succeed_on_stale_data': bool},
    inputs={'object': object},
    outputs={'attr': OptionRef('attr_type')},
    max_children=1))
class GetAttr(Decorator):
    def _do_setup(self):
        for child in self.children:
            child.setup()
            # We have a child, so set object to an empty object. We're avoiding an
            # error this way because we know what we're doing, don't use this
            # gratuitously!
            self.inputs['object'] = object()
        return NodeMsg.IDLE

    def _do_tick(self):
        # Tick child (if any) so it can produce its output before we process it
        for child in self.children:
            child.tick()

        if self.inputs.is_updated('object'):
            try:
                self.outputs['attr'] = getattr(self.inputs['object'],
                                               self.options['attr_name'])
                return NodeMsg.SUCCEEDED
            except AttributeError:
                self.logerr('Object %s does not have attribute %s'
                            % (self.inputs['object'], self.options['attr_name']))
                return NodeMsg.FAILED
        else:
            if self.options['succeed_on_stale_data']:
                return NodeMsg.SUCCEEDED
            else:
                self.loginfo('No new data since last tick!')
                return NodeMsg.RUNNING

    def _do_shutdown(self):
        pass

    def _do_reset(self):
        self.outputs['attr'] = None
        self.outputs.reset_updated()
        self.inputs['object'] = None
        self._do_setup()
        self.inputs.reset_updated()
        return NodeMsg.IDLE

    def _do_untick(self):
        return NodeMsg.IDLE
