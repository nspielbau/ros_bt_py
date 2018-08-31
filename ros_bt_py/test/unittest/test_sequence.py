from copy import deepcopy
import unittest

from ros_bt_py_msgs.msg import Node, UtilityBounds

from ros_bt_py.nodes.mock_nodes import MockLeaf, MockUtilityLeaf
from ros_bt_py.nodes.sequence import Sequence, MemorySequence


class TestSequence(unittest.TestCase):
    def setUp(self):
        self.succeeder = MockLeaf(name='succeeder',
                                  options={'output_type': int,
                                           'state_values': [Node.SUCCEEDED],
                                           'output_values': [1]})
        self.failer = MockLeaf(name='failer',
                               options={'output_type': int,
                                        'state_values': [Node.FAILED],
                                        'output_values': [1]})
        self.runner = MockLeaf(name='runner',
                               options={'output_type': int,
                                        'state_values': [Node.RUNNING],
                                        'output_values': [1]})

        self.cheap_fail = MockUtilityLeaf(
            name='cheap_fail',
            options={
                'utility_lower_bound_success': 5.0,
                'utility_upper_bound_success': 10.0,
                'utility_lower_bound_failure': 1.0,
                'utility_upper_bound_failure': 2.0})
        self.cheap_success = MockUtilityLeaf(
            name='cheap_success',
            options={
                'utility_lower_bound_success': 1.0,
                'utility_upper_bound_success': 2.0,
                'utility_lower_bound_failure': 5.0,
                'utility_upper_bound_failure': 10.0})

        self.sequence = Sequence()

    def tearDown(self):
        self.sequence.shutdown()

    def testEmptyTickFails(self):
        self.sequence.setup()
        self.sequence.tick()
        self.assertEqual(self.sequence.state, Node.FAILED)

    def testTickSuccess(self):
        self.sequence.add_child(self.succeeder)
        self.sequence.setup()
        self.sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(self.sequence.state, Node.SUCCEEDED)

    def testTickRunning(self):
        self.sequence.add_child(self.runner)
        self.sequence.add_child(self.succeeder)
        self.sequence.setup()
        self.sequence.tick()
        self.assertEqual(self.runner.outputs['tick_count'], 1)
        self.assertEqual(self.runner.state, Node.RUNNING)
        self.assertEqual(self.succeeder.outputs['tick_count'], 0)
        self.assertEqual(self.succeeder.outputs['untick_count'], 0)
        self.assertEqual(self.succeeder.state, Node.IDLE)
        self.assertEqual(self.sequence.state, Node.RUNNING)

    def testTickFailing(self):
        self.sequence.add_child(self.failer)
        self.sequence.add_child(self.succeeder)
        self.sequence.setup()
        self.sequence.tick()
        self.assertEqual(self.failer.outputs['tick_count'], 1)
        self.assertEqual(self.failer.state, Node.FAILED)
        self.assertEqual(self.succeeder.outputs['tick_count'], 0)
        self.assertEqual(self.succeeder.outputs['untick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.PAUSED)
        self.assertEqual(self.sequence.state, Node.FAILED)

    def testNested(self):
        inner_sequence = Sequence(name='inner')
        inner_sequence.add_child(self.succeeder)
        self.sequence.add_child(inner_sequence)
        self.sequence.setup()

        self.sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(inner_sequence.state, Node.SUCCEEDED)
        self.assertEqual(self.sequence.state, Node.SUCCEEDED)

    def testCalculateUtility(self):
        self.sequence.add_child(self.cheap_fail)

        self.assertEqual(self.sequence.calculate_utility(),
                         self.cheap_fail.calculate_utility())

        cheap_fail_2 = deepcopy(self.cheap_fail)
        cheap_fail_2.name = 'cheap_fail_2'
        self.sequence.add_child(cheap_fail_2)
        cheap_fail_bounds = self.cheap_fail.calculate_utility()
        expected_bounds = UtilityBounds(has_lower_bound_success=True,
                                        has_upper_bound_success=True,
                                        has_lower_bound_failure=True,
                                        has_upper_bound_failure=True)

        # Upper and lower bounds for success should be the sum of the
        # children's bounds
        expected_bounds.lower_bound_success = cheap_fail_bounds.lower_bound_success * 2.0
        expected_bounds.upper_bound_success = cheap_fail_bounds.upper_bound_success * 2.0
        # Lower bound for failure is the same as for a single node
        # (i.e. first child fails as cheaply as possible)
        expected_bounds.lower_bound_failure = cheap_fail_bounds.lower_bound_failure
        # Upper bound for failure is sum of upper *success* bounds for
        # all children but the last, plus upper *failure* bound for
        # the last child. In our case, that's one failing and one
        # succeeding child.
        expected_bounds.upper_bound_failure = (
            cheap_fail_bounds.upper_bound_success +
            cheap_fail_bounds.upper_bound_failure)

        self.assertEqual(self.sequence.calculate_utility(),
                         expected_bounds)

    def testUtilityWithDifferentChildren(self):
        self.sequence.add_child(self.cheap_success)
        self.sequence.add_child(self.cheap_fail)

        expected_bounds = UtilityBounds(has_lower_bound_success=True,
                                        has_upper_bound_success=True,
                                        has_lower_bound_failure=True,
                                        has_upper_bound_failure=True)

        cheap_success_bounds = self.cheap_success.calculate_utility()
        cheap_fail_bounds = self.cheap_fail.calculate_utility()
        expected_bounds.lower_bound_success = (
            cheap_success_bounds.lower_bound_success +  # 1.0
            cheap_fail_bounds.lower_bound_success)      # 5.0
        expected_bounds.upper_bound_success = (
            cheap_success_bounds.upper_bound_success +  # 2.0
            cheap_fail_bounds.upper_bound_success)      # 10.0
        expected_bounds.lower_bound_failure = (
            cheap_success_bounds.lower_bound_success +  # 1.0
            cheap_fail_bounds.lower_bound_failure)      # 1.0
        expected_bounds.upper_bound_failure = (
            cheap_success_bounds.upper_bound_failure)   # 10.0

        self.assertEqual(self.sequence.calculate_utility(),
                         expected_bounds)


class TestMemorySequence(unittest.TestCase):
    def setUp(self):
        self.succeeder = MockLeaf(name='succeeder',
                                  options={'output_type': int,
                                           'state_values': [Node.SUCCEEDED],
                                           'output_values': [1]})
        self.succeeder_2 = MockLeaf(name='succeeder_2',
                                    options={'output_type': int,
                                             'state_values': [Node.SUCCEEDED],
                                             'output_values': [1]})
        self.failer = MockLeaf(name='failer',
                               options={'output_type': int,
                                        'state_values': [Node.FAILED],
                                        'output_values': [1]})
        self.runner = MockLeaf(name='runner',
                               options={'output_type': int,
                                        'state_values': [Node.RUNNING],
                                        'output_values': [1]})

        self.cheap_fail = MockUtilityLeaf(
            name='cheap_fail',
            options={
                'utility_lower_bound_success': 5.0,
                'utility_upper_bound_success': 10.0,
                'utility_lower_bound_failure': 1.0,
                'utility_upper_bound_failure': 2.0})
        self.cheap_success = MockUtilityLeaf(
            name='cheap_success',
            options={
                'utility_lower_bound_success': 1.0,
                'utility_upper_bound_success': 2.0,
                'utility_lower_bound_failure': 5.0,
                'utility_upper_bound_failure': 10.0})

        self.mem_sequence = MemorySequence()

    def tearDown(self):
        self.mem_sequence.shutdown()

    def testEmptyTickFails(self):
        self.mem_sequence.setup()
        self.mem_sequence.tick()
        self.assertEqual(self.mem_sequence.state, Node.FAILED)

    def testTickSuccess(self):
        self.mem_sequence.add_child(self.succeeder)
        self.mem_sequence.add_child(self.succeeder_2)
        self.mem_sequence.setup()
        self.mem_sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(self.succeeder_2.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder_2.state, Node.SUCCEEDED)

        self.assertEqual(self.mem_sequence.state, Node.SUCCEEDED)

        # The MemorySequence finished execution, so it starts again at
        # the first child and ticks both its children one more time
        self.mem_sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 2)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(self.succeeder_2.outputs['tick_count'], 2)
        self.assertEqual(self.succeeder_2.state, Node.SUCCEEDED)

        self.assertEqual(self.mem_sequence.state, Node.SUCCEEDED)

    def testTickRunning(self):
        self.mem_sequence.add_child(self.runner)
        self.mem_sequence.add_child(self.succeeder)
        self.mem_sequence.setup()
        self.mem_sequence.tick()
        self.assertEqual(self.runner.outputs['tick_count'], 1)
        self.assertEqual(self.runner.state, Node.RUNNING)
        self.assertEqual(self.succeeder.outputs['tick_count'], 0)
        self.assertEqual(self.succeeder.outputs['untick_count'], 0)
        self.assertEqual(self.succeeder.state, Node.IDLE)
        self.assertEqual(self.mem_sequence.state, Node.RUNNING)

    def testTickRunningAfterSucceeder(self):
        self.mem_sequence.add_child(self.succeeder)
        self.mem_sequence.add_child(self.runner)
        self.mem_sequence.setup()
        self.mem_sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(self.runner.outputs['tick_count'], 1)
        self.assertEqual(self.runner.state, Node.RUNNING)
        self.assertEqual(self.mem_sequence.state, Node.RUNNING)

        # The MemorySequence should *NOT* tick the succeeder, since it
        # hasn't finished ticking all its children yet.
        self.mem_sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(self.runner.outputs['tick_count'], 2)
        self.assertEqual(self.runner.state, Node.RUNNING)
        self.assertEqual(self.mem_sequence.state, Node.RUNNING)

    def testTickFailing(self):
        self.mem_sequence.add_child(self.failer)
        self.mem_sequence.add_child(self.succeeder)
        self.mem_sequence.setup()
        self.mem_sequence.tick()
        self.assertEqual(self.failer.outputs['tick_count'], 1)
        self.assertEqual(self.failer.state, Node.FAILED)
        self.assertEqual(self.succeeder.outputs['tick_count'], 0)
        self.assertEqual(self.succeeder.outputs['untick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.PAUSED)
        self.assertEqual(self.mem_sequence.state, Node.FAILED)

        # second tick should start at the failer again
        self.mem_sequence.tick()
        self.assertEqual(self.failer.outputs['tick_count'], 2)
        self.assertEqual(self.failer.state, Node.FAILED)
        self.assertEqual(self.succeeder.outputs['tick_count'], 0)
        self.assertEqual(self.succeeder.outputs['untick_count'], 2)
        self.assertEqual(self.succeeder.state, Node.PAUSED)
        self.assertEqual(self.mem_sequence.state, Node.FAILED)

    def testTickFailingAfterSuccess(self):
        self.mem_sequence.add_child(self.succeeder)
        self.mem_sequence.add_child(self.failer)
        self.mem_sequence.setup()
        self.mem_sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(self.failer.outputs['tick_count'], 1)
        self.assertEqual(self.failer.state, Node.FAILED)
        self.assertEqual(self.mem_sequence.state, Node.FAILED)

        # The MemorySequence failed, so it starts over, ticking both
        # children again
        self.mem_sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 2)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(self.failer.outputs['tick_count'], 2)
        self.assertEqual(self.failer.state, Node.FAILED)
        self.assertEqual(self.mem_sequence.state, Node.FAILED)

    def testNested(self):
        inner_sequence = Sequence(name='inner')
        inner_sequence.add_child(self.succeeder)
        self.mem_sequence.add_child(inner_sequence)
        self.mem_sequence.setup()

        self.mem_sequence.tick()
        self.assertEqual(self.succeeder.outputs['tick_count'], 1)
        self.assertEqual(self.succeeder.state, Node.SUCCEEDED)
        self.assertEqual(inner_sequence.state, Node.SUCCEEDED)
        self.assertEqual(self.mem_sequence.state, Node.SUCCEEDED)

    def testCalculateUtility(self):
        self.mem_sequence.add_child(self.cheap_fail)

        self.assertEqual(self.mem_sequence.calculate_utility(),
                         self.cheap_fail.calculate_utility())

        cheap_fail_2 = deepcopy(self.cheap_fail)
        cheap_fail_2.name = 'cheap_fail_2'
        self.mem_sequence.add_child(cheap_fail_2)
        cheap_fail_bounds = self.cheap_fail.calculate_utility()
        expected_bounds = UtilityBounds(has_lower_bound_success=True,
                                        has_upper_bound_success=True,
                                        has_lower_bound_failure=True,
                                        has_upper_bound_failure=True)

        # Upper and lower bounds for success should be the sum of the
        # children's bounds
        expected_bounds.lower_bound_success = cheap_fail_bounds.lower_bound_success * 2.0
        expected_bounds.upper_bound_success = cheap_fail_bounds.upper_bound_success * 2.0
        # Lower bound for failure is the same as for a single node
        # (i.e. first child fails as cheaply as possible)
        expected_bounds.lower_bound_failure = cheap_fail_bounds.lower_bound_failure
        # Upper bound for failure is sum of upper *success* bounds for
        # all children but the last, plus upper *failure* bound for
        # the last child. In our case, that's one failing and one
        # succeeding child.
        expected_bounds.upper_bound_failure = (
            cheap_fail_bounds.upper_bound_success +
            cheap_fail_bounds.upper_bound_failure)

        self.assertEqual(self.mem_sequence.calculate_utility(),
                         expected_bounds)

    def testUtilityWithDifferentChildren(self):
        self.mem_sequence.add_child(self.cheap_success)
        self.mem_sequence.add_child(self.cheap_fail)

        expected_bounds = UtilityBounds(has_lower_bound_success=True,
                                        has_upper_bound_success=True,
                                        has_lower_bound_failure=True,
                                        has_upper_bound_failure=True)

        cheap_success_bounds = self.cheap_success.calculate_utility()
        cheap_fail_bounds = self.cheap_fail.calculate_utility()
        expected_bounds.lower_bound_success = (
            cheap_success_bounds.lower_bound_success +  # 1.0
            cheap_fail_bounds.lower_bound_success)      # 5.0
        expected_bounds.upper_bound_success = (
            cheap_success_bounds.upper_bound_success +  # 2.0
            cheap_fail_bounds.upper_bound_success)      # 10.0
        expected_bounds.lower_bound_failure = (
            cheap_success_bounds.lower_bound_success +  # 1.0
            cheap_fail_bounds.lower_bound_failure)      # 1.0
        expected_bounds.upper_bound_failure = (
            cheap_success_bounds.upper_bound_failure)   # 10.0

        self.assertEqual(self.mem_sequence.calculate_utility(),
                         expected_bounds)
