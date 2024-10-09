import cv2
import numpy as np
import urllib.request
import csv
import random
import string
import qrcode
from datetime import datetime
import requests
import json
import os
import asyncio
from final2 import WasteManagementSystem

class ESP32LiveTransmission:
    def __init__(self, url, thingspeak_write_api_key, thingspeak_read_api_key, thingspeak_channel_id):
        self.url = url
        self.thingspeak_write_api_key = thingspeak_write_api_key
        self.thingspeak_read_api_key = thingspeak_read_api_key
        self.thingspeak_channel_id = thingspeak_channel_id
        self.detector = cv2.QRCodeDetector()
        self.user_map = {}  # Dictionary to map unique IDs with Names

    def generate_unique_id(self, Name):
        initials = ''.join(word[0] for word in Name.split())
        random_number = ''.join(random.choices(string.digits, k=4))
        unique_id = initials.upper() + random_number
        return unique_id

    def generate_qr_code(self, data, file_name):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(file_name)

    def register_user(self, Name, phone_number, house_number, area, pincode, wallet_balance=0, credits=0):
        unique_id = self.generate_unique_id(Name)
        qr_code_data = f"Name: {Name}\nPhone: {phone_number}\nHouse: {house_number}\nArea: {area}\nPincode: {pincode}\nID: {unique_id}"

        # Generate QR code and save it
        self.generate_qr_code(qr_code_data, f"{unique_id}.png")

        # Store mapping of unique ID with Name
        self.user_map[unique_id] = Name

        # Send data to ThingSpeak
        payload = {
            'api_key': self.thingspeak_write_api_key,
            'field1': Name,
            'field2': phone_number,
            'field3': house_number
        }
        response = requests.post(f'https://api.thingspeak.com/update.json', data=payload)

        if response.status_code == 200:
            print("Data sent to ThingSpeak successfully!")
        else:
            print("Failed to send data to ThingSpeak.")

        # Write user details to CSV file
        file_exists = os.path.isfile('load_registrations.csv')
        header = ['Unique ID', 'Name', 'Phone Number', 'House Number', 'Area', 'Pincode', 'Wallet Balance', 'Credits']
        with open('load_registrations.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(header)
            writer.writerow([unique_id, Name, phone_number, house_number, area, pincode, wallet_balance, credits])

        print("User registered successfully!")
        print(f"Unique ID: {unique_id}")
        print("QR code generated successfully!")

    def capture_frame_with_qr(self, frame, file_name):
        cv2.imwrite(file_name, frame)
        print(f"Frame with QR code captured: {file_name}")

    async def view_details_through_qr(self):
        cv2.namedWindow("Live Transmission", cv2.WINDOW_AUTOSIZE)
        Name = None
        while True:
            img_resp = urllib.request.urlopen(self.url)
            imgnp = np.array(bytearray(img_resp.read()), dtype=np.uint8)
            frame = cv2.imdecode(imgnp, -1)

            # Detect QR codes
            decoded_data, _, _ = self.detector.detectAndDecode(frame)

            # Display details if QR code data detected
            if decoded_data:
                details = decoded_data.split('\n')
                if len(details) == 6:
                    Name = details[0][6:]
                    phone_number = details[1][7:]
                    house_number = details[2][7:]
                    area = details[3][6:]
                    pincode = details[4][9:]
                    print("\nUser Details:")
                    print(f"Name: {Name}")
                    print(f"Phone Number: {phone_number}")
                    print(f"House Number: {house_number}")
                    print(f"Area: {area}")
                    print(f"Pincode: {pincode}")

                    # Fetch additional data from ThingSpeak
                    response = requests.get(f'https://api.thingspeak.com/channels/{self.thingspeak_channel_id}/fields/1.json?api_key={self.thingspeak_read_api_key}&results=1')
                    if response.status_code == 200:
                        data = response.json()
                        print("Fetched data from ThingSpeak:")
                        print(json.dumps(data, indent=4))
                    else:
                        print("Failed to fetch data from ThingSpeak.")

                    with open('Final_registrations.csv', mode='a', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(["Name", "Phone Number", "House Number", "Area", "Pincode", "Date", "Time"])
                        writer.writerow([Name, phone_number, house_number, area, pincode, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S")])

                    break  # Exit the loop once details are printed

            cv2.imshow('Live Transmission', frame)
            key = cv2.waitKey(5)
            if key == ord('q'):
                break

        cv2.destroyAllWindows()
        return Name

    def append_waste_data(self, Name, avg_load, avg_trash_percentage):
        with open('load_registrations.csv', mode='r', newline='') as file:
            csv_reader = csv.reader(file)
            rows = list(csv_reader)

        found = False
        for row in rows:
            if row and row[0] == Name:
                # Sum up the previous and current values
                prev_avg_load = float(row[1]) if row[1] else 0
                prev_avg_trash_percentage = float(row[2]) if row[2] else 0
                row[1] = prev_avg_load + avg_load
                row[2] = prev_avg_trash_percentage + avg_trash_percentage
                found = True
                break

        if not found:
            rows.append([Name, avg_load, avg_trash_percentage])

        with open('load_registrations.csv', mode='w', newline='') as file:
            csv_writer = csv.writer(file)
            csv_writer.writerows(rows)

        payload = {
            'api_key': self.thingspeak_write_api_key,
            'field5': int(avg_load),
            'field6': int(avg_trash_percentage)
        }
        response = requests.post('https://api.thingspeak.com/update.json', data=payload)
        if response.status_code == 200:
            print("Waste data sent to ThingSpeak successfully!")
        else:
            print("Failed to send waste data to ThingSpeak.")

async def main():
    url = 'http://192.168.10.225/cam-hi.jpg'
    thingspeak_write_api_key = '5WVKI1PG8DLXCUB1'
    thingspeak_read_api_key = 'BUIKMPVX80ITSJZC'
    thingspeak_channel_id = '2492599'
    live_transmission = ESP32LiveTransmission(url, thingspeak_write_api_key, thingspeak_read_api_key, thingspeak_channel_id)
    system = WasteManagementSystem('/dev/cu.usbserial-130', '7047754135:AAG8fFEA1lDVe21bQYYTozv3gb_wpf3-5hs',
                                   '1893904443', '5WVKI1PG8DLXCUB1',
                                   'https://api.thingspeak.com/update')

    choice = input("Choose an option:\n1. Register user\n2. View details through QR code\n3. Place Trash")

    if choice == "1":
        Name = input("Enter your Name: ")
        phone_number = input("Enter your phone number: ")
        house_number = input("Enter your house number: ")
        area = input("Enter your area: ")
        pincode = input("Enter your pincode: ")
        live_transmission.register_user(Name, phone_number, house_number, area, pincode, wallet_balance=0, credits=0)
    elif choice == "2":
        await live_transmission.view_details_through_qr()
    elif choice == '3':
        # Capture user details from QR code
        Name = await live_transmission.view_details_through_qr()

        # Ensure the user's Name was captured
        if Name:
            # Start waste detection
            avg_load, avg_trash_percentage, detected_waste_type = await system.detect_waste()

            # Append waste management details to the user's entry in the CSV
            live_transmission.append_waste_data(Name, avg_load, avg_trash_percentage)
        else:
            print("Failed to retrieve user details through QR.")
    else:
        print("Invalid choice. Please choose 1, 2, or 3.")

if __name__ == '__main__':
    asyncio.run(main())
