from machine import Pin, PWM
import time
import network
import socket
import gc  # ソケット解放に必要

# --- Wi-Fi接続設定 ---
ssid = 'yourssid'
password = 'yourpass'
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)
while not wlan.isconnected():
    pass
print('Connected on', wlan.ifconfig()[0])

# --- モーター制御ピン設定 ---
ain1 = Pin(0, Pin.OUT)
ain2 = Pin(1, Pin.OUT)
pwma = PWM(Pin(2))
stby = Pin(3, Pin.OUT)
pwma.freq(1000)

# --- エンコーダ設定 ---
pulse_count = 0
last_a = 0
last_b = 0
PULSES_PER_REV = 48 * 8.5  # ギア比補正済み

def encoder_callback(pin):
    global pulse_count, last_a, last_b
    a = encoder_a.value()
    b = encoder_b.value()
    if pin == encoder_a:
        if a != last_a:
            pulse_count += 1 if a == b else -1
            last_a = a
    elif pin == encoder_b:
        if b != last_b:
            pulse_count += 1 if a != b else -1
            last_b = b

encoder_a = Pin(4, Pin.IN, Pin.PULL_UP)
encoder_b = Pin(5, Pin.IN, Pin.PULL_UP)
last_a = encoder_a.value()
last_b = encoder_b.value()
encoder_a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=encoder_callback)
encoder_b.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=encoder_callback)

# --- モーター制御関数 ---
def motor_forward(speed):
    stby.value(1)
    ain1.value(1)
    ain2.value(0)
    pwma.duty_u16(speed)

def motor_backward(speed):
    stby.value(1)
    ain1.value(0)
    ain2.value(1)
    pwma.duty_u16(speed)

def motor_stop():
    ain1.value(0)
    ain2.value(0)
    pwma.duty_u16(0)
    stby.value(0)

# --- PID & 制御パラメータ ---
Kp = 300.0
Ki = 1.0
Kd = 0.0
dt = 0.001
tau = 0.05
alpha = dt / (tau + dt)

desired_target_angle = 0
current_target_angle = 0
integral = 0
last_error = 0

# --- TCPサーバー初期化（EADDRINUSE対策込み）---
gc.collect()
time.sleep(0.2)

try:
    client.close()
except:
    pass
try:
    s.close()
except:
    pass

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 5000))
s.listen(1)
print("Waiting for TCP connection...")
client, addr = s.accept()
print("Connected from:", addr)
client.setblocking(False)

# --- メイン制御ループ ---
t_start = time.ticks_ms()
last_display_time = t_start

try:
    while True:
        # --- 角度目標の受信処理 ---
        try:
            data = client.recv(1024)
            if data:
                try:
                    new_angle = int(data.decode().strip())
                    desired_target_angle = new_angle
                    integral = 0
                except Exception as e:
                    pass
        except:
            pass

        # --- ローパスフィルタ ---
        current_target_angle = alpha * desired_target_angle + (1 - alpha) * current_target_angle

        # --- 現在角度計算 ---
        angle_deg = (pulse_count / PULSES_PER_REV) * 360.0

        # --- PID制御 ---
        error = current_target_angle - angle_deg
        integral += error * dt
        derivative = (error - last_error) / dt
        output = (Kp * error) + (Ki * integral) + (Kd * derivative)
        last_error = error

        # --- モーター駆動 ---
        if abs(error) < 0.1:
            motor_stop()
        else:
            duty = int(min(60000, max(5000, abs(output))))
            if output > 0:
                motor_forward(duty)
            else:
                motor_backward(duty)

        # --- 1行上書き表示（100msおき） ---
        t_now_ms = time.ticks_ms()
        if time.ticks_diff(t_now_ms, last_display_time) >= 100:
            # 誤差率の計算（分母が小さすぎるときは0にする）
            if abs(desired_target_angle) > 1e-3:
                error_rate = (error / desired_target_angle) * 100.0
            else:
                error_rate = 0.0

            print("Target:{:7.2f} Filtered:{:7.2f} Current:{:7.2f} Error%:{:6.2f}".format(
                desired_target_angle, current_target_angle, angle_deg, error_rate), end="\r")
            last_display_time = t_now_ms

        # --- 1ms周期 ---
        time.sleep_us(1000)

except KeyboardInterrupt:
    print("\nStopped by user.")
    motor_stop()
    try:
        client.close()
        s.close()
    except:
        pass
