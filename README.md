# Distance Based Control of Two Servos with ROS 2

This project measures distance with an HC-SR04 sensor and sets the positions of two SG90 servos. An Arduino Uno measures the echo pulse duration and generates the servo signals. A Raspberry Pi 5 runs two ROS 2 nodes in Docker: `arduino_bridge` transfers data between the Arduino and ROS, while `controller` selects the angles based on distance. A laptop is used to upload the firmware and access the Raspberry Pi over SSH.

This guide applies to the **two-servo version** of the project:

```text
two_servos/
├── README.md
├── arduino_bridge.py
├── controller.py
└── firmware_two_servos/
    └── firmware_two_servos.ino
```

## 1. Required Components

| Component | Purpose |
|---|---|
| Raspberry Pi 5 | Runs Docker and ROS 2 Jazzy |
| Arduino Uno | Reads the sensor, generates servo signals and communicates over USB |
| HC-SR04 | Measures distance |
| Two positional SG90 servos | Move to specified angles |
| External regulated 5 V supply | Powers both SG90 servos; its current capacity must support their combined load |
| Raspberry Pi power supply | Powers the Raspberry Pi itself |
| Laptop, USB data cable and jumper wires | Configuration, firmware upload and connections |

Our Raspberry Pi runs **Debian GNU/Linux 13 trixie, aarch64**. ROS 2 Jazzy runs inside a container based on `ros:jazzy-ros-base`. Debian remains the host operating system; a separate Ubuntu installation is not required. The official ROS image supports ARM64. [Official ROS image](https://hub.docker.com/_/ros)

## 2. Pin Connections

Disconnect the Arduino USB cable and the external servo supply before changing any wiring.

### HC-SR04 Sensor

| Sensor pin | Arduino Uno |
|---|---|
| VCC | 5V |
| GND | GND |
| TRIG | D7 |
| ECHO | D8 |

The sensor connects to the Arduino Uno. The Raspberry Pi GPIO pins are not used in this circuit.

### Two SG90 Servos

| Wire | Servo 1 | Servo 2 |
|---|---|---|
| Signal, usually orange or yellow | Arduino D9 | Arduino D10 |
| Power, usually red | External +5 V | External +5 V |
| Ground, usually brown or black | External supply negative | External supply negative |

Check the wire assignments for your particular servo. Connect **the external supply negative to Arduino GND**. Both servos and the Arduino need a common ground. When the Arduino is powered through USB, **do not connect the external +5 V to the Arduino 5V pin**. Do not power SG90 servos from 3.3V. [Power supplies and common ground — Arduino](https://support.arduino.cc/hc/en-us/articles/360018922259-What-power-supply-can-I-use-with-my-Arduino-board)

### Wiring and Power Diagram

```text
Raspberry Pi USB <======= USB data cable =======> Arduino Uno

Arduino 5V ------------------------------------ HC-SR04 VCC
Arduino D7 ------------------------------------ HC-SR04 TRIG
Arduino D8 ------------------------------------ HC-SR04 ECHO
Arduino D9 ------------------------------------ SG90 #1 SIGNAL
Arduino D10 ----------------------------------- SG90 #2 SIGNAL

External supply +5 V ----+---------------------- SG90 #1 VCC
                        +---------------------- SG90 #2 VCC

External supply GND ----+----------------------- SG90 #1 GND
                       +----------------------- SG90 #2 GND
                       +----------------------- Arduino GND
                       +----------------------- HC-SR04 GND
```

The `SIGNAL` wires carry position commands, while `VCC` and `GND` provide power. The laptop communicates with the Raspberry Pi over Wi-Fi using SSH. To upload firmware, temporarily connect the Arduino USB cable to the laptop.

## 3. Connecting to the Raspberry Pi from a Laptop

### Use the Same Network and the Correct Address

1. Connect the laptop and Raspberry Pi to the same Wi-Fi network, such as a phone hotspot. The Raspberry Pi must already have the network name and password configured.
2. Open PowerShell on the laptop.
3. In the commands below, replace `PI_USER` with your **Raspberry Pi username** and `PI_IP` with its current IP address. Use the password for that user account, not the Wi-Fi password.

For the hostname used in our setup:

```powershell
ssh PI_USER@rpi-server.local
```

If the hostname does not resolve, find the Raspberry Pi IP address in the hotspot or router client list:

```powershell
ssh PI_USER@PI_IP
```

The IP address shown in Windows Wi-Fi settings belongs to the laptop. The DNS field shows the DNS server address. Neither should be assumed to be the Raspberry Pi address. Once connected, use `hostname -I` to display the Raspberry Pi addresses.

On the first connection, check that the hostname or IP belongs to your Raspberry Pi, then accept the host key by entering `yes`. Password characters are not displayed while typing. A successful connection shows a prompt such as `username@rpi-server:~ $`. Commands entered there now run on the Raspberry Pi. [SSH and address discovery — Raspberry Pi](https://www.raspberrypi.com/documentation/computers/remote-access.html)

### If SSH Is Not Enabled Yet

On an existing Debian installation with access to its local terminal:

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

Run these commands **on the Raspberry Pi**, not in Windows PowerShell. If you cannot access the Pi yet, initial system configuration is required. For a new Raspberry Pi OS installation, Raspberry Pi Imager can configure Wi-Fi, the username, hostname and SSH before booting. An already configured Pi, as used in this project, does not need to be reinstalled.

## 4. Uploading the Arduino Firmware

1. If the nodes are running, stop both with `Ctrl+C` in their terminals.
2. Save the previous sketch if you need it. Uploading replaces the firmware on the Uno.
3. Disconnect the servo supply and connect the Arduino to the laptop with a USB data cable.
4. Open `firmware_two_servos/firmware_two_servos.ino` in Arduino IDE.
5. Select the **Arduino Uno** board and its **COM port**.
6. Click **Upload**. If the IDE reports that `Servo.h` is missing, install the **Servo** library through Library Manager.
7. Close Serial Monitor. Reconnect the Arduino to the Raspberry Pi USB port, then turn on the servo supply.

The firmware is stored on the Arduino. The Python nodes are stored on the Raspberry Pi. Editing a Python file does not replace the Uno firmware.

## 5. Installing ROS 2 on the Raspberry Pi with Docker

Complete this section once. If the image and container are already configured, continue to Section 8.

Run all commands in this section **over SSH on the Raspberry Pi**. Internet access is required for installation.

### Check the Operating System

```bash
cat /etc/os-release
uname -m
```

Our environment reports Debian 13 trixie and `aarch64`.

### Install Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-cli
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

These are Debian packages: `docker.io` provides the engine and `docker-cli` provides the command-line client. [Docker packages in Debian 13](https://packages.debian.org/trixie/docker.io)

### Download ROS 2 Jazzy

```bash
sudo docker pull ros:jazzy-ros-base
sudo docker run --rm ros:jazzy-ros-base ros2 --help
```

`ros:jazzy-ros-base` is the base image. The custom image created below is named `ros2-arduino:jazzy`, and the running container is named `ros2-arduino`.

### Create the Workspace and Dockerfile

```bash
mkdir -p ~/ros2_arduino_ws/src
cd ~/ros2_arduino_ws
nano Dockerfile
```

Paste the following into `Dockerfile`:

```dockerfile
FROM ros:jazzy-ros-base
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-serial \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /ws
```

In nano, save with `Ctrl+O`, press `Enter`, then exit with `Ctrl+X`.

Build the image from this directory:

```bash
sudo docker build -t ros2-arduino:jazzy .
```

The final dot refers to the current directory containing the Dockerfile. The bridge needs `python3-serial` for USB serial communication with the Uno.

## 6. Copying the Python Files to the Raspberry Pi

Use `arduino_bridge.py` and `controller.py` from the **two_servos** directory next to this README.

If the files already exist on the Pi, first stop both nodes and back up the directory **over SSH**:

```bash
cp -a ~/ros2_arduino_ws/src ~/ros2_arduino_ws/src_backup_$(date +%Y%m%d_%H%M%S)
```

On the laptop, open PowerShell in the directory containing the two Python files. In the current workspace, use:

```powershell
cd "C:\Users\Victus\Documents\Codex\2026-09-27\new-chat\outputs\two_servos"
scp arduino_bridge.py controller.py PI_USER@rpi-server.local:~/ros2_arduino_ws/src/
```

Replace `PI_USER` with your username. On another computer, use your own directory containing these files. If `.local` does not resolve, replace the hostname with the Raspberry Pi IP address.

Verify the files **over SSH**:

```bash
ls -l ~/ros2_arduino_ws/src/
```

Both `arduino_bridge.py` and `controller.py` should be present.

## 7. Connecting the Arduino to Docker

### Find the USB Device

Connect the Uno to the Raspberry Pi and run **over SSH**:

```bash
ls -l /dev/serial/by-id/
```

The Arduino in our setup had this identifier:

```text
usb-Arduino__www.arduino.cc__0043_5583834363335191F050-if00 -> ../../ttyACM0
```

For another board, use the name shown in your own output. Inside the container, the port will be available as `/dev/arduino`.

### Create the Container Once

First check whether the container exists:

```bash
sudo docker ps -a --filter name=ros2-arduino
```

If `ros2-arduino` already exists, do not create it again; continue to Section 8. Otherwise, run the commands below. Set the first line to your Arduino device identifier:

```bash
ARDUINO_DEVICE='/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_5583834363335191F050-if00'

sudo docker run -d \
  --name ros2-arduino \
  --init \
  --device="$ARDUINO_DEVICE":/dev/arduino \
  --mount type=bind,source="$HOME/ros2_arduino_ws",target=/ws \
  ros2-arduino:jazzy sleep infinity
```

`--device` grants the container access to the specified USB device. `--mount` maps `~/ros2_arduino_ws` on the Pi to `/ws` inside the container. Editing a Python file on the Pi therefore updates the file that the container runs. [docker run options](https://docs.docker.com/reference/cli/docker/container/run/)

`sleep infinity` keeps the container running; the ROS nodes are started separately. Both nodes run in this same container.

## 8. Starting the Two ROS 2 Nodes

Open **two PowerShell windows on the laptop**. Connect to the Pi in each window:

```powershell
ssh PI_USER@rpi-server.local
```

Run the following commands in those SSH terminals.

### Prepare the Container

Run once before starting the nodes:

```bash
sudo docker start ros2-arduino
```

If the Arduino was disconnected from USB or its firmware was uploaded again, use this instead of `start`:

```bash
sudo docker restart ros2-arduino
```

Restarting stops the processes inside the container. Start both nodes again afterwards.

### Terminal 1 — Arduino Bridge

```bash
sudo docker exec -it ros2-arduino bash -lc 'source /opt/ros/jazzy/setup.bash && python3 /ws/src/arduino_bridge.py'
```

After opening the port, the bridge waits approximately two seconds for the Uno to reset. Leave this terminal running.

### Terminal 2 — Controller

```bash
sudo docker exec -it ros2-arduino bash -lc 'source /opt/ros/jazzy/setup.bash && python3 /ws/src/controller.py'
```

Leave the second terminal running. Do not start another instance of either node at the same time.

`source` loads the ROS 2 environment for the process. The nodes in this project are run directly as Python scripts, so they do not require `ros2 run` or `colcon build`. A separate `roscore` command is not needed either.

### Check the Nodes in a Third SSH Terminal

```bash
sudo docker exec -it ros2-arduino bash
source /opt/ros/jazzy/setup.bash
ros2 node list
ros2 topic list
ros2 topic echo /distance
```

The expected node names are `/arduino_bridge` and `/controller`. Values on `/distance` are in centimetres. A value of `-1` indicates an invalid measurement.

Press `Ctrl+C` to stop displaying distances, then inspect the commands:

```bash
ros2 topic echo /motor_command
```

`Ctrl+C` stops the topic display. `exit` leaves the container shell and returns to the Pi SSH shell. Run diagnostic `ros2` commands inside the container after loading the ROS environment.

## 9. Working Principle and Messages

### Data Flow Diagram

```text
HC-SR04 --> Arduino -- USB, D,distance --> arduino_bridge
                                               |
                                   /distance, Float32, cm
                                               |
                                               v
                                           controller
                                               |
                                   /motor_command, String
                                               |
                                               v
SG90 #1 and #2 <-- Arduino <-- USB, C,angle1,angle2 <-- arduino_bridge
```

1. The Arduino sends a TRIG pulse and measures the ECHO pulse duration. Distance in centimetres is `echo_duration_us × 0.0343 / 2`.
2. Approximately every 100 ms, the Arduino sends a newline-terminated string such as `D,25.4`. The software accepts distances from 2 to 400 cm; an invalid measurement is sent as `D,-1`.
3. `arduino_bridge` reads the serial port at **115200 baud** and publishes the distance on `/distance` using `std_msgs/msg/Float32`.
4. `controller` subscribes to `/distance`. It selects the positions and publishes a command every 0.2 seconds on `/motor_command` using `std_msgs/msg/String`.
5. The bridge subscribes to `/motor_command`, validates the values and forwards the string to the Arduino. The Arduino sets both angles using the Servo library.

| Condition | Command | Servo 1 | Servo 2 |
|---|---|---:|---:|
| Distance below 20 cm | `C,45,135` | 45° | 135° |
| Distance above 25 cm | `C,90,90` | 90° | 90° |
| From 20 to 25 cm inclusive | Previous command | Keep position | Keep position |
| Invalid or stale data | `S` | Disable control signal | Disable control signal |

Using different activation and return thresholds is called **hysteresis**. It reduces switching caused by small measurement fluctuations. The controller starts in the “far” state, so an initial valid measurement between 20 and 25 cm produces a 90°/90° command.

Repeating a command sets the same absolute angles; it does not add another rotation. The servos should remain at their selected positions while the object is stationary.

The controller checks data freshness and sends `S` after one second without a new measurement. The bridge checks the freshness of commands and valid readings using a 0.8-second threshold. The firmware also disables the signals if commands are missing for more than 1.2 seconds or valid measurements for more than one second. With `S`, servo power remains connected, but control pulses are disabled; position holding is not guaranteed. `S` does not mean “return to 90°”.

## 10. Checking the System Before a Demonstration

1. Make sure both servos can move freely.
2. Start the bridge and controller.
3. Place an object approximately 10 cm from the sensor: expect 45° and 135°.
4. Move the object to approximately 30 cm: expect 90° and 90°.
5. Hold the object still: the servos should not swing continuously.
6. Check `/distance` and `/motor_command` if the response differs from expectations.

The table above describes the expected software behaviour. The logic was checked with simulated ROS and Arduino interfaces; use these steps to verify the physical behaviour of your assembled hardware.

## 11. Changing the Distances and Angles

### Open the Controller

Over SSH on the Raspberry Pi:

```bash
nano ~/ros2_arduino_ws/src/controller.py
```

Alternatively, install the **Remote - SSH** extension in VS Code on the laptop. Open **View → Command Palette → Remote-SSH: Connect to Host**, connect to `PI_USER@rpi-server.local` and open `/home/PI_USER/ros2_arduino_ws`, replacing `PI_USER` with your username. This edits the files directly on the Pi. [Remote SSH in VS Code](https://code.visualstudio.com/docs/remote/ssh)

### Change the Distance Thresholds

Find this block in `on_distance`:

```python
if distance < 20.0:
    self.opened = True
elif distance > 25.0:
    self.opened = False
```

For example, to activate below 10 cm and return above 15 cm, replace `20.0` with `10.0` and `25.0` with `15.0`. Values are in centimetres. The return threshold must be greater than the activation threshold.

### Change the Angles

Find this block in `send_command`:

```python
elif self.opened:
    command = 'C,45,135'
else:
    command = 'C,90,90'
```

The format is `C,servo1_angle,servo2_angle`. For example, `C,60,120` sets the first servo to 60° and the second to 120°. The current code limits both angles to **30–150°**. The bridge and firmware reject values outside this range. Changing the limits themselves requires matching changes in both the bridge and firmware, followed by uploading the updated firmware to the Uno.

Save with `Ctrl+O → Enter → Ctrl+X`. In the controller terminal, press `Ctrl+C` and repeat the `controller.py` launch command from Section 8. Leave the bridge running. Changing ordinary thresholds or angles within the allowed range does not require rebuilding Docker or uploading Arduino firmware again.

## 12. Starting Again and Shutting Down

Once installation is complete, use this sequence before a class:

1. Power on the Pi, connect the Uno to it and turn on the servo supply.
2. Connect the laptop and Pi to the same network.
3. Open two SSH terminals.
4. Run `sudo docker start ros2-arduino`; after reconnecting USB, use `sudo docker restart ros2-arduino`.
5. Start the bridge in the first terminal and the controller in the second using the commands in Section 8.

To stop, press `Ctrl+C` in the controller terminal and then in the bridge terminal. Stop the container if required:

```bash
sudo docker stop ros2-arduino
```

Before disconnecting Raspberry Pi power, run **over SSH on the Pi**:

```bash
sudo poweroff
```

Wait for shutdown to finish. Disconnect the external servo supply.

## 13. Troubleshooting

| Symptom | What to check |
|---|---|
| SSH `Connection timed out` | Current Pi IP address, connection to the same network and whether the hotspot isolates clients |
| SSH `Connection refused` | Confirm that the responding device is the Pi and that SSH is enabled; the phone or DNS server address is not the Pi address |
| `.local` name does not resolve | Connect using the current Raspberry Pi IP address |
| `ros2: command not found` | Run the command inside the ROS container after `source /opt/ros/jazzy/setup.bash` |
| `No such container: ros2-arduino` | The container has not been created; see Section 7 |
| Container name is already in use | Do not repeat `docker run`; use the existing container |
| `/dev/arduino` is missing or a USB I/O error occurs | Check power, the cable and `/dev/serial/by-id/`; stop the nodes, reconnect the Uno and restart the container |
| Servos jitter or the Uno resets | Check the 5 V servo supply, its current capacity, common ground, wiring and the SG90 units themselves |
| Repeated `D,-1` or `/distance: -1` | Check sensor VCC/GND, TRIG D7, ECHO D8, object distance and the reflecting surface |
| Nothing moves | Confirm that both nodes are running, valid readings and servo power are present, and signal wires connect to D9/D10 |

### SSH Host Key Change Warning

`REMOTE HOST IDENTIFICATION HAS CHANGED` means the device key differs from the saved key. Simply changing Wi-Fi networks does not change the SSH key. First verify the device identity: for example, compare the fingerprint with the output of `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` obtained through trusted local access to the Pi. The fingerprint in the warning itself is not independent verification.

After confirming that the new key belongs to your Raspberry Pi, for example after reinstalling its system, remove the old entry **in PowerShell on the laptop**:

```powershell
ssh-keygen -R rpi-server.local
ssh PI_USER@rpi-server.local
```

If the warning names an IP address, pass that exact address to `ssh-keygen -R`. Accept the new key after verification. Do not delete the entire `known_hosts` file or disable host key checking. [ssh-keygen options](https://man.openbsd.org/ssh-keygen)
