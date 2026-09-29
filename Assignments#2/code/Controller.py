import math
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String
    

class Controller(Node):
    def __init__(self):
        super().__init__('controller')

        self.publisher = self.create_publisher(
            String, '/motor_command', 10
        )
        self.subscription = self.create_subscription(
            Float32, '/distance', self.on_distance, 10
        )

        self.opened = False
        self.valid = False
        self.last_received = 0.0
        self.previous_command = None

        self.timer = self.create_timer(0.2, self.send_command)
        self.get_logger().info('Controller started.')

    def on_distance(self, msg):
        distance = msg.data
        self.last_received = time.monotonic()

        self.valid = (
            math.isfinite(distance)
            and 2.0 <= distance <= 400.0
        )

        if not self.valid:
            return

        if distance < 20.0:
            self.opened = True
        elif distance > 30.0:
            self.opened = False

    def send_command(self):
        fresh = time.monotonic() - self.last_received < 1.0

        if not self.valid or not fresh:
            command = 'S'
        elif self.opened:
            command = 'C,45,512'
        else:
            command = 'C,90,0'

        msg = String()
        msg.data = command
        self.publisher.publish(msg)

        if command != self.previous_command:
            self.get_logger().info(f'Command: {command}')
            self.previous_command = command


def main():
    rclpy.init()
    node = Controller()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
