import inspect
import sys
from threading import Thread
import time
import unittest

from ros_bt_py_msgs.msg import Node as NodeMsg

from ros_bt_py.debug_manager import DebugManager
from ros_bt_py.nodes.passthrough_node import PassthroughNode


class TestDebugManager(unittest.TestCase):
    def setUp(self):
        self.manager = DebugManager()

    def testReport(self):
        self.manager._debug_settings_msg.collect_performance_data = True

        node = PassthroughNode(name='foo',
                               options={'passthrough_type': int})
        node.setup()

        starting_recursion_depth = len(inspect.stack())
        with self.manager.report_tick(node):
            time.sleep(0.01)

        self.assertEqual(self.manager.get_debug_info_msg().max_recursion_depth,
                         sys.getrecursionlimit())
        # Plus one for the context self.manager, and another one for the contextlib decorator
        self.assertEqual(self.manager.get_debug_info_msg().current_recursion_depth,
                         starting_recursion_depth + 2)

    def testStep(self):
        self.manager._debug_settings_msg.single_step = True

        self.node = PassthroughNode(name='foo',
                                    options={'passthrough_type': int},
                                    debug_manager=self.manager)
        self.node.setup()
        self.node.inputs['in'] = 1

        def do_stuff():
            self.node.tick()

        test_thread = Thread(target=do_stuff)
        test_thread.start()
        time.sleep(0.05)

        # Thread should be blocked on first continue -> the output does not
        # have a value yet.
        self.assertEqual(self.node.outputs['out'], None)
        self.assertEqual(self.node.state, NodeMsg.DEBUG_PRE_TICK)
        self.assertTrue(test_thread.isAlive())
        self.manager.continue_debug()
        time.sleep(0.05)

        # Now out should be changed
        self.assertEqual(self.node.outputs['out'], 1)
        self.assertEqual(self.node.state, NodeMsg.SUCCEEDED)
        # Should still be waiting for second continue -> join won't work
        test_thread.join(0.01)
        self.assertTrue(test_thread.isAlive())

        # Continue to DEBUG_POST_TICK - this is only to show in the tree where
        # the debug handler is - no other changes since the previous continue
        self.manager.continue_debug()
        time.sleep(0.05)
        self.assertEqual(self.node.state, NodeMsg.DEBUG_POST_TICK)
        self.manager.continue_debug()
        # This join should work
        test_thread.join(0.01)
        self.assertFalse(test_thread.isAlive())
        # The node state should be restored after the last continue
        self.assertEqual(self.node.state, NodeMsg.SUCCEEDED)
