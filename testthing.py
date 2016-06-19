#!/usr/bin/python3

# Commands list: http://www.madreporite.com/insteon/commands.htm
import serial, binascii,time, json, logging, threading, pickle
import testlib as insteon
import queue

logging.basicConfig(level=logging.DEBUG)
MODEM = bytearray([0x39,0x54,0xbf])


ser = serial.Serial(
                    port='/dev/ttyUSB0', #'/dev/ttyUSB0'
                    baudrate=19200,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=8
                    )

ser.reset_input_buffer()
ser.reset_output_buffer()

lock = threading.Lock()
q = queue.Queue()
insteon.setModemMonitor(ser,False,lock)

testlist = insteon.getLinks(ser, lock)
for item in testlist:
    print(testlist[item])
print("Going to get devinfo")
prelist = {}
try:
    with open("test_devices.json", "r") as infile:
        prelist = json.load(infile)
except:
    pass
devlist = {}
devices = {}
for item in testlist:
    print(item)
    if item in prelist:
        devlist[item] = prelist[item]
        devices[item] = insteon.Device(**prelist[item])
    else:
        response = insteon.getDeviceID(ser,testlist[item], lock)
        print(response)
        devlist[item] = response
        devices[item] = insteon.Device(**response)
with open("test_devices.json", "w") as outfile:
    json.dump(devlist, outfile)
    outfile.close()
print(devlist)
print(devices)

insteon.setModemMonitor(ser,True,lock)
#
