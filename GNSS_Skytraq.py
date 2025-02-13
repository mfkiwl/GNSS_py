#!/usr/bin/python3
import binascii
import copy
import multiprocessing.queues
import os
import struct
import time
import py7zr

import requests
import serial

import bme280
import smbus2


#############################################################
############ SKYTRAQ FUNCTION HERE ##########################
#############################################################
def zipfile(dir, dest):
    # subprocess.run("7z a -o{" + dir + "} -t7z " + dir + "/" + dest + ".7z " + dir + "/" + dest + ".dat -m9=LZMA2 -aoa",
    #                shell=True)
    zip_path = dir + "/" + dest + ".7z"
    zipObj = py7zr.SevenZipFile(dir + "/" + dest + ".7z", 'w')
    zipObj.writeall(dir + "/" + dest + ".dat", dest+".dat")
    zipObj.writeall(dir + "/" + dest + ".csv", dest+".csv")
    zipObj.close()

    if os.path.exists(dir + "/" + dest + ".7z"):
        print("DELETE FILE HERE")
        os.system("rm " + dir + "/" + dest + ".dat")
        os.system("rm " + dir + "/" + dest + ".csv")
    else:
        print("7z running")
    os.system("/home/gnss/gdrive upload --parent 1clJ40gbolVktoYmWukR0TDLOaLI4GgVV " + zip_path)
    #os.system("/home/gnss/gdrive about > /home/gnss/gdrive.log")
    print("UPLOADED")
#############################################################


############ REQUEST FUNCTION ###############################
############ to send data to server #########################
#############################################################
def stqSend():
    while True:
        # print("sending", not q.empty())
        if not q.empty():
            stq_data = q.get()
            data = {
                "data": stq_data[0],
                "time": stq_data[1] * 604800 + round(stq_data[2]),
                "GPS_Week": stq_data[1],
                "stationID": "60cc71512c850461b8693d93",
                "temperature": stq_data[3],
                "atmospheric_pressure": stq_data[4],
                "humidity": stq_data[5]
            }
            try:
                x = requests.post(import_url, data=data)
                #print(x, "\t time=", stq_data[2], "\t size=", len(stq_data[0]), "\t", q.qsize(), stq_data[3:6])
            except Exception as err:
                print(err.args)

        time.sleep(0.3)


#############################################################
############ SKYTRAQ FUNCTION HERE ##########################
#############################################################

def stqGetTow(bytes, type):
    if type == 0xDF:
        return struct.unpack('>d', bytes[9:17])[0]
    if type == 0xE5:
        return int.from_bytes(bytes[9:13], "big")/1000


def stqGetWN(bytes, type):
    if type == 0xDF or type == 0xE5:
        return int.from_bytes(bytes[7:9], "big")


########### A little variables ##############################
home_path = "/home/gnss/"
SERIAL_PORT = '/dev/ttyS3'
SERIAL_RATE = 115200
gpsSerial = serial.Serial(SERIAL_PORT, SERIAL_RATE)

import_url = 'http://112.137.134.7:5000/data'

port = 0
address = 0x76
try:
    bus = smbus2.SMBus(port)
    calibration_params = bme280.load_calibration_params(bus, address)
except Exception as err:
    print(err.args)

q = multiprocessing.Queue()
send_msg = ''

wn = ((int(time.time()) - 315964782 - 18) // 60 // 60 // 24 // 7)
day = 8

try:
    os.mkdir(home_path + str(wn))
except Exception as err:
    print(err.args)
log_file = open(home_path + str(wn) + "/" + str(wn) + "_" + str(day) + ".dat", "ab")
sen_file = open(home_path + str(wn) + "/" + str(wn) + "_" + str(day) + ".csv", "a")

############ here to run send process #######################
multiprocessing.Process(target=stqSend).start()
#############################################################
############ MAIN FUNCTION HERE #############################
#############################################################
while True:
    msg = gpsSerial.read_until(b'\x0d\x0a')
    msg_type = int.from_bytes(msg[4:5], "big")
    msg_len = int.from_bytes(msg[2:4], "big")

    while msg_len > len(msg) - 7:
        # print("\t WARNING: too short | " + str(msg_len) + " " + str(len(msg)), end="\t")
        msg += gpsSerial.read_until(b'\x0d\x0a')
        # print(len(msg))

    send_msg += binascii.hexlify(msg).decode('utf-8').upper()

    if msg_type == 0xE5:
        cur_wn = stqGetWN(msg, msg_type)
        cur_tow = stqGetTow(msg, msg_type)
        cur_day = (int(cur_tow)) // 60 // 60 // 24 % 7
        #cur_day = (int(cur_tow)) // 300  
        if cur_day != day or cur_wn != wn:
            multiprocessing.Process(target=zipfile, args=(
                copy.deepcopy(home_path + str(wn)), copy.deepcopy(str(wn) + "_" + str(day)))).start()
            day = cur_day
            wn = cur_wn
            try:
                os.mkdir(home_path + str(wn))
            except Exception as err:
                print(err.args)
            log_file.close()
            sen_file.close()
            log_file = open(home_path + str(wn) + "/" + str(wn) + "_" + str(day) + ".dat", "ab")
            sen_file = open(home_path + str(wn) + "/" + str(wn) + "_" + str(day) + ".csv", "a")
        try:
            bmedata = bme280.sample(bus, address, calibration_params)
        except Exception as err:
            print(err.args)
            bmedata = None

        if bmedata != None:
            q.put([send_msg, wn, stqGetTow(msg, msg_type), bmedata.temperature, bmedata.pressure, bmedata.humidity])
            sen_file.write(str(cur_wn*60*60*24*7 + cur_tow)+","+str(round(bmedata.temperature, 4))+", "+str(round(bmedata.pressure, 4))+", "+str(round(bmedata.humidity, 4))+"\n")
        else:
            q.put([send_msg, wn, stqGetTow(msg, msg_type), 0, 0, 0])
        send_msg = ''
        #print(hex(msg_type) + " " + str(wn) + " " + str(day) + " " + str(cur_tow+1))
    log_file.write(msg)
    log_file.flush()
    sen_file.flush()
    os.fsync(log_file.fileno())
    os.fsync(sen_file.fileno())
    time.sleep(0.1)
