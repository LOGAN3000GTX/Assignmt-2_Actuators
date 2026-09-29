"""ROS 2 bridge: /distance in cm, /motor_command = S or C,angle,target."""
import math
import re
import time

import serial
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String


class ArduinoBridge(Node):
    def __init__(self):
        super().__init__('arduino_bridge')
        self.port = serial.Serial('/dev/arduino', 115200, timeout=0,
                                  write_timeout=0.1, exclusive=True)
        time.sleep(2)
        self.port.reset_input_buffer()
        self.publisher = self.create_publisher(Float32, '/distance', 10)
        self.subscription = self.create_subscription(
            String, '/motor_command', self.on_command, 10)
        self.buffer = bytearray()
        self.last_command = 0.0
        self.last_valid_range = 0.0
        self.timer = self.create_timer(0.01, self.read_sensor)
        self.watchdog = self.create_timer(0.2, self.check_connection)
        self.send('S')
        self.get_logger().info('Arduino ready: distance + motor commands.')

    def send(self, command):
        self.port.write((command + '\n').encode('ascii'))

    def on_command(self, msg):
        command = msg.data.strip()
        if command == 'S':
            self.last_command = time.monotonic()
            self.send('S')
            return
        match = re.fullmatch(r'C,(\d{1,3}),(\d{1,3})', command)
        if not match:
            self.get_logger().warning('Rejected malformed motor command.')
            return
        angle, target = map(int, match.groups())
        if not (30 <= angle <= 150 and 0 <= target <= 512):
            self.get_logger().warning('Rejected motor command outside limits.')
            return
        now = time.monotonic()
        self.last_command = now
        self.send(command if now - self.last_valid_range < 0.8 else 'S')

    def read_sensor(self):
        self.buffer.extend(self.port.read(min(self.port.in_waiting, 1024)))
        while b'\n' in self.buffer:
            raw, _, remaining = self.buffer.partition(b'\n')
            self.buffer = bytearray(remaining)
            line = raw.decode('ascii', errors='replace').strip()
            if not line.startswith('D,'):
                continue
            try:
                distance = float(line[2:])
            except ValueError:
                continue
            valid = math.isfinite(distance) and 2.0 <= distance <= 400.0
            if valid:
                self.last_valid_range = time.monotonic()
            else:
                distance = -1.0
                self.last_valid_range = 0.0
                self.send('S')
            msg = Float32()
            msg.data = distance
            self.publisher.publish(msg)
        if len(self.buffer) > 256:
            self.buffer.clear()

    def check_connection(self):
        now = time.monotonic()
        if now - self.last_command > 0.8 or now - self.last_valid_range > 0.8:
            self.send('S')

    def close(self):
        try:
            if self.port.is_open:
                self.send('S')
        finally:
            self.port.close()


def main():
    rclpy.init()
    node = None
    try:
        node = ArduinoBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            try:
                node.close()
            finally:
                node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
