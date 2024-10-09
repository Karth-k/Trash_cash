import cv2
import csv
from datetime import datetime
import serial
import requests
from telegram import Bot
from Model import WasteDetector
import signal
import asyncio

class WasteManagementSystem:
    def __init__(self, serial_port, telegram_token, chat_id, thingspeak_key, thingspeak_url):
        self.serial_port = serial.Serial(serial_port, 9600)
        self.bot = Bot(token=telegram_token)
        self.chat_id = chat_id
        self.thingspeak_key = thingspeak_key
        self.thingspeak_url = thingspeak_url
        signal.signal(signal.SIGINT, self.safe_exit)

    async def send_telegram_message(self, message, image_path):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_message = f'{message}\nTime: {current_time}\nLocation: https://maps.app.goo.gl/S1mBNRsD4z28P4rc7'

        # Send the message
        await self.bot.send_message(chat_id=self.chat_id, text=full_message)

        # Send the image
        with open(image_path, 'rb') as image_file:
            await self.bot.send_photo(chat_id=self.chat_id, photo=image_file)

    def write_to_thingspeak(self, data):
        payload = {'api_key': self.thingspeak_key, 'field1': data}
        response = requests.post(self.thingspeak_url, data=payload)
        print("ThingSpeak Response:", response.text)

    # def log_formatted_data(self, load, trash_percentage, waste_type):
    #     with open('load_registrations.csv', mode='a', newline='') as file:
    #         writer = csv.writer(file)
    #         if file.tell() == 0:
    #             writer.writerow(["Average Load", "Average Trash Percentage", "Detected Waste Type", "Time"])
    #         writer.writerow([load, trash_percentage, waste_type,
    #                          datetime.now().strftime("%H:%M:%S")])

    def safe_exit(self, signum, frame):
        self.close()
        print("Safely shutting down...")
        exit(0)

    def close(self):
        print("Closing serial port and exiting system...")
        self.serial_port.close()

    async def detect_waste(self):
        load_values = []
        trash_percentages = []
        count = 0
        avg_load = 0.0  # Default value if no loads are detected
        avg_trash_percentage = 0.0  # Default value if no percentages are detected
        detected_waste_type = None  # Default value if no waste is detected

        while True:
            serial_data = self.serial_port.readline().decode().strip()
            data_list = serial_data.split(': ')
            if len(data_list) == 2:
                sensor_name, sensor_value = data_list

                if sensor_name == "Load sensor value" and 'g' in sensor_value:
                    numeric_value = float(sensor_value.replace('g', '').strip())
                    load_values.append(abs(numeric_value))
                    print(f"{sensor_name}: {abs(numeric_value)} g")

                elif sensor_name == "Trash percentage in dustbin":
                    percentage = float(sensor_value.replace('%', '').strip())
                    trash_percentages.append(percentage)
                    print(f"{sensor_name}: {percentage} %")

                count += 1

                if count >= 50:
                    avg_load = sum(load_values) / len(load_values) if load_values else 0.0
                    avg_trash_percentage = sum(trash_percentages) / len(trash_percentages) if trash_percentages else 0.0

                    detector = WasteDetector('http://192.168.10.225/cam-hi.jpg')
                    image, detected_waste_type = detector.detect_waste()  # Remove 'await' here
                    image_path = 'detected_waste.jpg'
                    cv2.imwrite(image_path, image)

                    if detected_waste_type:
                        waste_message = f"Detected: {detected_waste_type}"
                        await self.send_telegram_message(waste_message, image_path)
                        self.write_to_thingspeak(1 if 'Wet' in detected_waste_type else 2)
                        # self.log_formatted_data(f"{avg_load:.1f} g", f"{avg_trash_percentage:.2f} %",
                        #                         detected_waste_type)
                        print(waste_message)
                        break  # Exit the loop once waste is detected

        self.close()
        print(
            f"Avg Load: {avg_load:.2f} g, Avg Trash: {avg_trash_percentage:.2f}%, Predicted Waste Type: {detected_waste_type}")
        return avg_load, avg_trash_percentage, detected_waste_type


async def main():
    system = WasteManagementSystem('/dev/cu.usbserial-130', '7047754135:AAG8fFEA1lDVe21bQYYTozv3gb_wpf3-5hs',
                                   '1893904443', '5WVKI1PG8DLXCUB1',
                                   'https://api.thingspeak.com/update')
    await system.detect_waste()

if __name__ == '__main__':
    asyncio.run(main())
