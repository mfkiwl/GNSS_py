import copy
import os
import time

import serial
import binascii
import queue

from rtcmSend import rtcmSend


def getbitu(buff, pos, length):
    bits = 0
    for i in range(pos, pos + length):
        bits = (bits << 1) + ((buff[i // 8] >> (7 - i % 8)) & 1)
    return bits


def extractGPSTime(data, rtcmType):
    i = 24
    # rtcmType = getbitu(data, i, 12)
    i += 12;
    # / *decode rtcm3 message * /

    if rtcmType in {1074, 1075, 1076, 1077, 1094, 1095, 1096, 1097, 1104, 1105, 1106, 1107, 1114, 1115, 1116, 1117}:
        # print("GPS TYPE")
        i += 12
        tow = getbitu(data, i, 30) * 0.001
        i += 30
        return int(tow)

    if rtcmType in range(1124, 1127):
        # print("BEIDOU")
        i += 12;
        tow = getbitu(data, i, 30) * 0.001;
        i += 30;
        i += 1;
        return int(tow + 14)
    return -1


def ByteToHexStr(byte):
    return binascii.hexlify(byte).decode('utf-8').upper()


def bytes_to_int(bytes):
    result = 0
    for b in bytes:
        result = result * 256 + int(b)
    return result


def getSingleRtcmMsg():
    dropMsg, rtcmFullmsg, rtcmDataFrame = [], [], []
    msgByteCount, rtcmId, rtcmLength = 0, 0, 0
    while True:
        nowByte = int(ByteToHexStr(gpsSerial.read(1)), base=16)
        if msgByteCount == 0:
            if nowByte == 0xA0:  # 0xD3
                if len(dropMsg) != 0:
                    print("[UNKNOWN] : ", end="")
                    print(dropMsg)
                    dropMsg = []
            else:
                dropMsg.append(nowByte)
                print("---", dropMsg)
                continue
        elif msgByteCount == 1:
            rtcmLength = (nowByte & 3) << 8
        elif msgByteCount == 2:
            rtcmLength += nowByte
        elif msgByteCount <= 2 + rtcmLength:
            rtcmDataFrame.append(nowByte)
        # elif (msgByteCount > 2 + rtcmLength) and (msgByteCount <= (2 + rtcmLength) + 2):
        # 여기는 CRC 앞 두바이트
        elif msgByteCount == (2 + rtcmLength) + 3:
            rtcmFullmsg.append(nowByte)  # CRC 마지막 한바이트
            rtcmId = rtcmFullmsg[3]
            rtcmId = rtcmId << 4
            rtcmId = rtcmId | ((rtcmFullmsg[4] >> 4) or 15)
            hex = ''.join('%02x' % b for b in rtcmFullmsg)
            return [rtcmFullmsg, rtcmDataFrame, rtcmId, hex]
        msgByteCount += 1
        rtcmFullmsg.append(nowByte)


###########################################################
###################### MAIN FUNCTION HERE #################
###########################################################

SERIAL_PORT = '/dev/ttyUSB0'
SERIAL_RATE = 115200
gpsSerial = serial.Serial(SERIAL_PORT, SERIAL_RATE)

rtcmExplain = {1005: "Stationary RTK reference station ARP", 1074: "GPS MSM4", 1077: "GPS MSM7", 1084: "GLONASS MSM4",
               1087: "GLONASS MSM7", 1094: "Galileo MSM4", 1097: "Galileo MSM7", 1124: "BeiDou MSM4",
               1127: "BeiDou MSM7", 1230: "GLONASS code-phase biases",
               4072: "Reference station PVT (u-blox proprietary RTCM Message)"}

queue = queue.Queue()
thread1 = rtcmSend(queue)
thread1.start()
msg = ''
week = ((int(time.time()) - 315964782 - 18) // 60 // 60 // 24 // 7)

daytime = [86400, 172800, 259200, 345600, 432000, 518400, 604800]
date = ((int(time.time()) - 315964782 - 18) // 60 // 60 // 24 % 7)

tow = -1
weekChange = False;
try:
    os.mkdir("/home/fang/send/" + str(week))
except:
    print("folder exist")
log_file = open("/home/fang/send/" + str(week) + "/" + str(week) + "_" + str(date) + ".dat", "ab")

while True:
    print("OK")
    rtcmMsg = getSingleRtcmMsg()
    log_file.write(bytes(rtcmMsg[0]))
    if rtcmMsg[2] == 1005:
        data = [msg, week, copy.deepcopy(tow)]
        queue.put(data)
        msg = ''
    else:
        tow = extractGPSTime(rtcmMsg[0], rtcmMsg[2])
        if tow == 0:
            date = 0
            week += 1
            try:
                os.mkdir("/home/fang/send/" + str(week))
            except:
                print("folder exist")
            log_file.close()
            log_file = open("/home/fang/send/" + str(week) + "/" + str(week) + "_" + str(date) + ".dat", "ab")
            print("date has change 1 ", tow)
        elif tow >= daytime[date]:
            date += 1
            log_file.close()
            log_file = open("/home/fang/send/" + str(week) + "/" + str(week) + "_" +str(date) + ".dat", "ab")
            print("date has change 2 ", tow)
    msg += rtcmMsg[3]
