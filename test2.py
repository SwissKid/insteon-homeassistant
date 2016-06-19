#!/usr/bin/python3
import serial, binascii,time, json, logging, threading, queue
import testlib as insteon

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
ser.write(bytearray([0x02,0x62,0x00,0x00,0x00,0xCF,0x19,0x00]))
ser.read(8).strip()
while True:
    try:
        print(binascii.hexlify(ser.read(11).strip()))
    except:
        break
