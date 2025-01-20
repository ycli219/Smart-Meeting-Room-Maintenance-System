from flask import Flask, jsonify
from flask_cors import CORS
import threading
import time
import paho.mqtt.client as mqtt  
import base64
import json
import cv2
from skimage.metrics import structural_similarity as ssim

app = Flask(__name__)
CORS(app)

# B 房間的資料（靜態展示用，peopleCount 每秒增加）
room_b_data = {
    "roomName": "會議室 B",
    "active": True,
    "peopleCount": 0,
    "indicators": {
        "桌椅弄亂": False,
        "電器未關": False,
        "垃圾滿溢": False
    }
}

MQTT_SERVER = "172.20.10.8"  
MQTT_PORT = 1883  
MQTT_ALIVE = 60  
MQTT_TOPIC = "msg/toA"

pre_people = 0
check = True
last_check_time = None

def compare_images_with_threshold(img_path1, img_path2):
    img1 = cv2.imread(img_path1)
    img2 = cv2.imread(img_path2)

    if img1 is None or img2 is None:
        print("無法讀取圖片，請確認檔案路徑是否正確！")
        return

    img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    score, diff = ssim(img1_gray, img2_gray, full=True)
    return score

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    # print(f"{msg.topic}: {msg.payload.decode('utf-8')}"
    data = json.loads(msg.payload)
    msg_type = data.get("type")

    if msg_type == "text":
        people = data['# of people']
        global room_b_data
        room_b_data['peopleCount'] = people
        print(f"人數： {room_b_data['peopleCount']}")
        color = data['color']
        # print(color)
        global pre_people
        global check
        global last_check_time
        if pre_people > 0 and people == 0:
            check = True
        if pre_people == 0 and people > 0:
            print("不用關電風扇了")
            room_b_data["indicators"]["電器未關"] = False
            check = False
        
        if check and last_check_time is None:
            last_check_time = time.time()
        
        if check and last_check_time and (time.time() - last_check_time >= 2) and (color == 'r' or color == 'y'):
            print("請關電風扇")
            room_b_data["indicators"]["電器未關"] = False


        if not check:
            last_check_time = None
        pre_people = people

    elif msg_type == "image":
        if data['filename'] == '0.jpg':
            print(f"收到 樹莓派 的圖片，檔案名稱: {data['filename']}")
            image_data = base64.b64decode(data['content'])
            with open(f"../front/src/received_{data['filename']}", "wb") as image_file:
                image_file.write(image_data)
            print(f"圖片已儲存為 received_{data['filename']}")

            score = compare_images_with_threshold("../front/src/received_GT.jpg", "../front/src/received_0.jpg")
            print(score)
            if score <= 0.85:
                if not check:
                    print("不用整理桌椅")
                    room_b_data["indicators"]["桌椅弄亂"] = False
                else:
                    print(f"請整理桌椅: {score}")
                    room_b_data["indicators"]["桌椅弄亂"] = True
            else:
                print("不用整理桌椅")
                room_b_data["indicators"]["桌椅弄亂"] = False
        
        elif data['filename'] == 'GT.jpg':
            print(f"收到 樹莓派 的圖片，檔案名稱: {data['filename']}")
            image_data = base64.b64decode(data['content'])
            with open(f"../front/src/received_{data['filename']}", "wb") as image_file:
                image_file.write(image_data)
            print(f"圖片已儲存為 received_{data['filename']}")
    elif msg_type == "text2":
        distance = data['distance']
        if distance < 24:
            print(f"垃圾滿🪽: {distance}")
            room_b_data["indicators"]["垃圾滿溢"] = False
        else:
            room_b_data["indicators"]["垃圾滿溢"] = False
        # print(distance)
    else:
        print("收到未知類型的訊息:", data)



@app.route('/room/B', methods=['GET'])
def get_room_b():
    return jsonify(room_b_data), 200

# def test():
#     """每秒增加一次 peopleCount 的函式"""
#     while True:
#         time.sleep(1)  # 等待 1 秒
#         room_b_data["peopleCount"] += 1  # 增加人數
#         print(f"會議室 B 的人數已更新為: {room_b_data['peopleCount']}")  # 日誌輸出
#         room_b_data["indicators"]["桌椅弄亂"] = not room_b_data["indicators"]["桌椅弄亂"]
#         print(f"會議室 B 的桌椅狀況: {room_b_data['indicators']['桌椅弄亂']}")  # 日誌輸出
#         room_b_data["indicators"]["電器未關"] = not room_b_data["indicators"]["電器未關"]
#         print(f"會議室 B 的電器狀況: {room_b_data['indicators']['電器未關']}")  # 日誌輸出
#         room_b_data["indicators"]["垃圾滿溢"] = not room_b_data["indicators"]["垃圾滿溢"]
#         print(f"會議室 B 的垃圾狀況: {room_b_data['indicators']['垃圾滿溢']}")  # 日誌輸出
        
def mqtt_thread():
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE)  
    mqtt_client.loop_forever()

if __name__ == '__main__':
    # 啟動背景執行緒
    testing_thread = threading.Thread(target=mqtt_thread)
    testing_thread.daemon = True  # 設定為 daemon 執行緒，隨主程式結束而結束
    testing_thread.start()
    
    # 啟動 Flask 伺服器
    app.run(host='0.0.0.0', port=4999)
