from ros_bt_py_msgs.msg import Node as NodeMsg
from ros_bt_py_msgs.msg import UtilityBounds

from ros_bt_py.node import FlowControl, define_bt_node
from ros_bt_py.node_config import NodeConfig


@define_bt_node(NodeConfig(
    options={},
    inputs={},
    outputs={},
    max_children=None))
class Fallback(FlowControl):
    """Flow control node that succeeds when any one of its children succeeds.

    At every call of :meth:`tick`, it ticks all of its children in
    order until one of three things happens:

    1. A node returns SUCCEEDED:

       In this case, the Fallback also returns SUCCEEDED, and calls
       :meth:`ros_bt_py.node.Node.untick` on all remaining children.

    2. A node returns RUNNING:

       Just as with FAILED, the Fallback will also return RUNNING, but
       not call :meth:`ros_bt_py.node.Node.untick` on the remaining
       children until the RUNNING node produces a result. This
       prevents thrashing when there's multiple nodes that take a tick
       or two to produce a result.

    3. All nodes return FAILED:

       The Fallback will also return FAILED.

    *Special case:*

    If a Fallback has no children, its :meth:`tick` method will always
    return FAILED.
    """
    def _do_setup(self):
        for child in self.children:
            child.setup()

    def _do_tick(self):
        if not self.children:
            self.logwarn('Ticking without children. Is this really what you want?')
            return NodeMsg.FAILED

        # If we've previously succeeded or failed, untick all children
        if self.state in [NodeMsg.SUCCEEDED, NodeMsg.FAILED]:
            for child in self.children:
                child.untick()

        # Tick children until one returns SUCCEEDED or RUNNING
        for index, child in enumerate(self.children):
            result = child.tick()
            if result == NodeMsg.SUCCEEDED or result == NodeMsg.RUNNING:
                if result == NodeMsg.SUCCEEDED:
                    # untick all children after the one that triggered this
                    # condition
                    for untick_child in self.children[index + 1:]:
                        untick_child.untick()
                return result
        # If all children failed, we too fail
        return NodeMsg.FAILED

    def _do_untick(self):
        for child in self.children:
            child.untick()
        return NodeMsg.IDLE

    def _do_reset(self):
        for child in self.children:
            child.reset()
        return NodeMsg.IDLE

    def _do_shutdown(self):
        for child in self.children:
            child.shutdown()

    def _do_calculate_utility(self):
        bounds = UtilityBounds(has_lower_bound_success=False,
                               has_upper_bound_success=False,
                               has_lower_bound_failure=True,
                               lower_bound_failure=0.0,
                               has_upper_bound_failure=True,
                               upper_bound_failure=0.0)
        if self.children:
            # To figure out the best and worst case cost for success and
            # failure, respectively, we need to figure out the cheapest and
            # most expensive paths to success/failure.

            # Since there's only one path to failure (all children fail) we're
            # dealing with that first: It's the sum of all children's
            # upper/lower failure bounds.

            # Success is a little trickier: Any number of children may fail
            # before the first success. So we need to find the max and min
            # values of all possible combinations of success and failure:

            # The nth element in this represents the case where the nth child
            # succeeds. So for two children A and B, the lower and upper bounds
            # for success of the fallback would be as follows:
            #
            # lower bounds: [A.lower_success, (A.lower_failure + B.lower_success)]
            # upper bounds: [A.upper_success, (A.upper_failure + B.upper_success)]
            have_bounds = True
            success_bounds = [UtilityBounds(has_lower_bound_success=False,
                                            lower_bound_success=0,
                                            has_upper_bound_success=False,
                                            upper_bound_success=0)
                              for _ in self.children]
            for index, child_bounds in enumerate((child.calculate_utility()
                                                  for child in self.children)):
                # We can only provide an estimate if all children have an estimate
                # TODO(nberg): Maybe relax this?
                have_bounds = (have_bounds and
                               child_bounds.has_lower_bound_success and
                               child_bounds.has_upper_bound_success and
                               child_bounds.has_lower_bound_failure and
                               child_bounds.has_upper_bound_failure)

                bounds.has_lower_bound_failure &= child_bounds.has_lower_bound_failure
                bounds.lower_bound_failure += child_bounds.lower_bound_failure
                bounds.has_upper_bound_failure &= child_bounds.has_upper_bound_failure
                bounds.upper_bound_failure += child_bounds.upper_bound_failure

                success_bounds[index].lower_bound_success += child_bounds.lower_bound_success
                success_bounds[index].upper_bound_success += child_bounds.upper_bound_success
                # Range returns an empty range if the first parameter is larger
                # than the second, so no bounds checking necessary
                for i in range(index+1, len(success_bounds)):
                    success_bounds[i].lower_bound_success += child_bounds.lower_bound_failure
                    success_bounds[i].upper_bound_success += child_bounds.upper_bound_failure

            # Select the minimum and maximum values to get the final bounds
            bounds.lower_bound_success = min((x.lower_bound_success for x in success_bounds))
            bounds.upper_bound_success = max((x.upper_bound_success for x in success_bounds))

            # Check if we actually have bounds
            bounds.has_lower_bound_success = have_bounds
            bounds.has_upper_bound_success = have_bounds
            bounds.has_lower_bound_failure = have_bounds
            bounds.has_upper_bound_failure = have_bounds

        return bounds


@define_bt_node(NodeConfig(
    options={},
    inputs={},
    outputs={},
    max_children=None))
class MemoryFallback(FlowControl):
    """Flow control node that succeeds when any one of its children succeeds and has a memory.

    At every call of :meth:`tick`, it ticks all of its children in
    order until one of three things happens:

    1. A node returns SUCCEEDED:

       In this case, the Fallback also returns SUCCEEDED, and calls
       :meth:`ros_bt_py.node.Node.untick` on all remaining children.

    2. A node returns RUNNING:

       Just as with FAILED, the Fallback will also return RUNNING, but
       not call :meth:`ros_bt_py.node.Node.untick` on the remaining
       children until the RUNNING node produces a result. This
       prevents thrashing when there's multiple nodes that take a tick
       or two to produce a result.

    3. All nodes return FAILED:

       The Fallback will also return FAILED.

    The *Memory* part of the node means that after a child returns
    RUNNING, the execution will start at that same child on the next
    tick. This means that changes in the previous nodes' outcomes will
    not influence the execution of later children until either a) this
    node receives an `untick()` or b) the sequence returns SUCCEEDED
    or FAILED as described above.

    *Special case:*

    If a Fallback has no children, its :meth:`tick` method will always
    return FAILED.
    """
    def _do_setup(self):
        self.last_running_child = 0
        for child in self.children:
            child.setup()

    def _do_tick(self):
        if not self.children:
            self.logwarn('Ticking without children. Is this really what you want?')
            return NodeMsg.FAILED

        # If we've previously succeeded or failed, untick all children
        if self.state in [NodeMsg.SUCCEEDED, NodeMsg.FAILED]:
            for child in self.children:
                child.untick()

        # Tick children until one returns SUCCEEDED or RUNNING
        for index, child in enumerate(self.children):
            if index < self.last_running_child:
                continue
            result = child.tick()
            if result == NodeMsg.SUCCEEDED or result == NodeMsg.RUNNING:
                if result == NodeMsg.RUNNING:
                    self.last_running_child = index
                elif result == NodeMsg.SUCCEEDED:
                    # untick all children after the one that triggered this
                    # condition
                    for untick_child in self.children[index + 1:]:
                        untick_child.untick()
                return result
        # If all children failed, we too fail
        self.last_running_child = 0
        return NodeMsg.FAILED

    def _do_untick(self):
        for child in self.children:
            child.untick()
        self.last_running_child = 0
        return NodeMsg.IDLE

    def _do_reset(self):
        for child in self.children:
            child.reset()
        self.last_running_child = 0
        return NodeMsg.IDLE

    def _do_shutdown(self):
        for child in self.children:
            child.shutdown()
        self.last_running_child = 0

    def _do_calculate_utility(self):
        bounds = UtilityBounds(has_lower_bound_success=False,
                               has_upper_bound_success=False,
                               has_lower_bound_failure=True,
                               lower_bound_failure=0.0,
                               has_upper_bound_failure=True,
                               upper_bound_failure=0.0)
        if self.children:
            # To figure out the best and worst case cost for success and
            # failure, respectively, we need to figure out the cheapest and
            # most expensive paths to success/failure.

            # Since there's only one path to failure (all children fail) we're
            # dealing with that first: It's the sum of all children's
            # upper/lower failure bounds.

            # Success is a little trickier: Any number of children may fail
            # before the first success. So we need to find the max and min
            # values of all possible combinations of success and failure:

            # The nth element in this represents the case where the nth child
            # succeeds. So for two children A and B, the lower and upper bounds
            # for success of the fallback would be as follows:
            #
            # lower bounds: [A.lower_success, (A.lower_failure + B.lower_success)]
            # upper bounds: [A.upper_success, (A.upper_failure + B.upper_success)]
            have_bounds = True
            success_bounds = [UtilityBounds(has_lower_bound_success=False,
                                            lower_bound_success=0,
                                            has_upper_bound_success=False,
                                            upper_bound_success=0)
                              for _ in self.children]
            for index, child_bounds in enumerate((child.calculate_utility()
                                                  for child in self.children)):
                # We can only provide an estimate if all children have an estimate
                # TODO(nberg): Maybe relax this?
                have_bounds = (have_bounds and
                               child_bounds.has_lower_bound_success and
                               child_bounds.has_upper_bound_success and
                               child_bounds.has_lower_bound_failure and
                               child_bounds.has_upper_bound_failure)

                bounds.has_lower_bound_failure &= child_bounds.has_lower_bound_failure
                bounds.lower_bound_failure += child_bounds.lower_bound_failure
                bounds.has_upper_bound_failure &= child_bounds.has_upper_bound_failure
                bounds.upper_bound_failure += child_bounds.upper_bound_failure

                success_bounds[index].lower_bound_success += child_bounds.lower_bound_success
                success_bounds[index].upper_bound_success += child_bounds.upper_bound_success
                # Range returns an empty range if the first parameter is larger
                # than the second, so no bounds checking necessary
                for i in range(index+1, len(success_bounds)):
                    success_bounds[i].lower_bound_success += child_bounds.lower_bound_failure
                    success_bounds[i].upper_bound_success += child_bounds.upper_bound_failure

            # Select the minimum and maximum values to get the final bounds
            bounds.lower_bound_success = min((x.lower_bound_success for x in success_bounds))
            bounds.upper_bound_success = max((x.upper_bound_success for x in success_bounds))

            # Check if we actually have bounds
            bounds.has_lower_bound_success = have_bounds
            bounds.has_upper_bound_success = have_bounds
            bounds.has_lower_bound_failure = have_bounds
            bounds.has_upper_bound_failure = have_bounds

        return bounds
