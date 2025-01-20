'''
import paho.mqtt.client as mqtt  
import json
import random
import subprocess
import base64
import time

MQTT_SERVER = "192.168.0.171"
MQTT_PORT = 1883  
MQTT_ALIVE = 60  
TOPIC_FROM_B = "msg/toC"  # 接收 B 的訊息
TOPIC_TO_A = "msg/toA"    # 發送給 A 的訊息

pre_people = 0
check = False
last_check_time = None

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe(TOPIC_FROM_B)

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)['# of people']
    print(data)
    global pre_people
    global check
    global last_check_time
    if pre_people > 0 and data == 0:
      check = True
    if pre_people == 0 and data > 0:
      check = False
    
    if check and last_check_time is None:
        last_check_time = time.time()

    if check and last_check_time and (time.time() - last_check_time >= 5):
      subprocess.run(["/usr/bin/libcamera-jpeg", "-o", "0.jpg"])
      image_path = "0.jpg"
      with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
      payload = { "type": "image", "filename": "0.jpg", "content": encoded_string }
      mqtt_client.publish(TOPIC_TO_A, json.dumps(payload))

      check = False
    
    if not check:
        last_check_time = None

    pre_people = data
    
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE)

GT = 0
if GT == 0:
  subprocess.run(["/usr/bin/libcamera-jpeg", "-o", "GT.jpg"])
  image_path = "GT.jpg"
  with open(image_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
  payload = { "type": "image", "filename": "GT.jpg", "content": encoded_string }
  mqtt_client.publish(TOPIC_TO_A, json.dumps(payload))
  GT = 1

mqtt_client.loop_forever()
'''

import paho.mqtt.client as mqtt  
import json
import random
import subprocess
import base64
import time
import RPi.GPIO as GPIO
import threading

MQTT_SERVER = "192.168.0.171"
MQTT_PORT = 1883  
MQTT_ALIVE = 60  
TOPIC_FROM_B = "msg/toC"  # 接收 B 的訊息
TOPIC_TO_A = "msg/toA"    # 發送給 A 的訊息
SIG_PIN = 23

GPIO.setmode(GPIO.BCM)

pre_people = 0
check = False
last_check_time = None

def get_distance():
    # 設置 SIG 為輸出，發送觸發脈衝
    GPIO.setup(SIG_PIN, GPIO.OUT)
    GPIO.output(SIG_PIN, GPIO.LOW)
    time.sleep(0.002)  # 確保低電位穩定
    GPIO.output(SIG_PIN, GPIO.HIGH)
    time.sleep(0.00001)  # 10 微秒高脈衝
    GPIO.output(SIG_PIN, GPIO.LOW)

    # 設置 SIG 為輸入，等待回波信號
    GPIO.setup(SIG_PIN, GPIO.IN)

    # 等待回波開始 (超時保護)
    timeout_start = time.time()
    while GPIO.input(SIG_PIN) == 0:
        pulse_start = time.time()
        if (pulse_start - timeout_start) > 0.02:  # 20ms 超時
            print("等待回波開始超時！")
            return None

    # 等待回波結束 (超時保護)
    timeout_start = time.time()
    while GPIO.input(SIG_PIN) == 1:
        pulse_end = time.time()
        if (pulse_end - timeout_start) > 0.02:  # 20ms 超時
            print("等待回波結束超時！")
            return None

    # 計算距離
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17000  # 速度340m/s，除以2
    return round(distance, 2)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe(TOPIC_FROM_B)

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)['# of people']
    print(data)
    global pre_people
    global check
    global last_check_time
    if pre_people > 0 and data == 0:
      check = True
    if pre_people == 0 and data > 0:
      check = False
    
    if check and last_check_time is None:
        last_check_time = time.time()

    if check and last_check_time and (time.time() - last_check_time >= 5):
      subprocess.run(["/usr/bin/libcamera-jpeg", "-o", "0.jpg"])
      image_path = "0.jpg"
      with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
      payload = { "type": "image", "filename": "0.jpg", "content": encoded_string }
      mqtt_client.publish(TOPIC_TO_A, json.dumps(payload))

      check = False
    
    if not check:
        last_check_time = None

    pre_people = data
  
def send_distance_periodically():
    while True:
        distance = get_distance()
        if distance is not None:
            payload = {"type": "text2", "distance": distance}
            mqtt_client.publish(TOPIC_TO_A, json.dumps(payload))
            print(f"傳送距離: {distance} 公分")
        else:
            print("測距失敗")
        time.sleep(2)  # 每 2 秒測量一次距離

def send_image():
  while True:
    subprocess.run(["/usr/bin/libcamera-jpeg", "-o", "0.jpg"])
    image_path = "0.jpg"
    with open(image_path, "rb") as image_file:
      encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    payload = { "type": "image", "filename": "0.jpg", "content": encoded_string }
    mqtt_client.publish(TOPIC_TO_A, json.dumps(payload))
    time.sleep(10)
    
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE)

GT = 0
if GT == 0:
  subprocess.run(["/usr/bin/libcamera-jpeg", "-o", "GT.jpg"])
  image_path = "GT.jpg"
  with open(image_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
  payload = { "type": "image", "filename": "GT.jpg", "content": encoded_string }
  mqtt_client.publish(TOPIC_TO_A, json.dumps(payload))
  GT = 1

# 啟動背景執行緒
distance_thread = threading.Thread(target=send_distance_periodically)
distance_thread.daemon = True  # 設為守護進程，隨主程式退出
distance_thread.start()


image_thread = threading.Thread(target=send_image)
image_thread.daemon = True  # 設為守護進程，隨主程式退出
image_thread.start()

mqtt_client.loop_forever()

