#!/usr/bin/python3

import serial, binascii,time, json, logging, threading, pickle
import queue

logging.basicConfig(level=logging.DEBUG)
MODEM = bytearray([0x39,0x54,0xbf])
class Device:
    def __init__(self,commandQueue, ser, lock, hexaddr, category, subcategory, name="", linkdata="", linkflag=""):
        self._ser = ser
        self._lock = lock
        self._q = commandQueue
        self.hexid = hexaddr
        self.linkdata = linkdata
        self.linkflag = linkflag
        self._category = category
        self._subcategory = subcategory
        self.name = name
        self._on = False
        self._brightness = 0

    def update_state(self, on, level=0):
        self._on = on
        self._brightness = level

    def turn_on(self, brightness=255):
        logging.info("Turning light on")
        ba = bytearray([0x02,0x62])
        ba.extend(bytearray.fromhex(self.hexid))
        ba.extend(bytearray([0x0F,0x11,brightness]))
        self._on=True
        self._q.put(ba)
        return True

    def turn_off(self):
        logging.info("Turning light off")
        ba = bytearray([0x02,0x62])
        ba.extend(bytearray.fromhex(self.hexid))
        ba.extend(bytearray([0x0F,0x13,0x00]))
        self._on = False
        self._q.put(ba)
        return True

    def update(self):
        logging.info("Updating " + self.hexid)
        return
        ##If I were a better person, i'd write all this in the queue thingy, and have it handle different commands...
        #if self._q.empty():
        #    self._q.put({"device": self.hexid, "command": "status"})
        #    return True
        #else:
        #    return False

    def jsonme(self):
        return json.dumps({"hexaddr": self.hexid, "category": self._category, "subcategory": self._subcategory, "name": self.name})


class serWatcher(threading.Thread):
    def __init__(self, ser, serlock, devices, q):
        threading.Thread.__init__(self)
        self.ser= ser
        self.lock = serlock
        self.devices = devices
        self.q = q

    def run(self):
        while True:
                with self.lock:
                    if self.ser.in_waiting > 0:
                        string = self.ser.read(2).strip()
                        logging.debug("Read a line")
                        self.checkLine(string)
                    elif not self.q.empty():
                        line = self.q.get()
                        if type(line) == dict:
                            logging.debug("Command to be run")
                            self.runCommand(**line)
                            continue
                        elif type(line) != bytearray:
                            logging.error("Line is not bytearray")
                            continue ##Ignore command
                        logging.debug("Gonna write a line")
                        logging.debug(binascii.hexlify(line))
                        self.ser.write(line)
                        test = self.ser.read(len(line) + 1) ##Check ack
                        line.append(0x06)
                        if test != line:
                            logging.error("Failed on writing: " + binascii.hexlify(line[:-1]))
                    else:
                        continue
    def runCommand(self, device, command):
        if command == "status":
            logging.debug("Status command for: "+device)
            ba = bytearray([0x02,0x62])
            ba.extend(bytearray.fromhex(device))
            ba.extend(bytearray([0x0F,0x19,0x00]))
            self.ser.write(ba)
            test = self.ser.read(len(ba) + 1).strip() ##Check ack
            ba.append(0x06)
            if test != ba:
                logging.error("Failed on writing: " + binascii.hexlify(line[:-1]))
                return
            string = self.ser.read(11).strip()
            self.devices[device]._brightness = int(string[10])
            logging.debug("Updated " + device + " And the brightness is " + str(self.devices[device]._brightness))
            if self.devices[device]._brightness == 0:
                self.devices[device]._on = False
    def checkLine(self, ba):
        if ba == bytearray([0x02,0x50]): #Standard insteon message
            string=self.ser.read(9).strip()
            logging.debug("Standard Insteon Line")
            logging.debug(binascii.hexlify(string))
            self.standardLineParse(string)
        elif ba == bytearray([0x02,0x51]): #Extended insteon message
            string=self.ser.read(23).strip()
            logging.debug("Extended Insteon Line")
            logging.debug(binascii.hexlify(string))
        elif ba == bytearray([0x02,0x52]): #X10 Message
            string=self.ser.read(2).strip()
            logging.debug("X10 Line")
            logging.debug(binascii.hexlify(string))
        else:
            logging.debug(binascii.hexlify(ba))
    def X10Parse(self, ba):
        pass
    def standardLineParse(self, ba):
#2e89fd3954bf451301
        src = ba[0:3]
        dst = ba[3:6]
        devname = ''.join('{:02x}'.format(x) for x in src)
        msgType = ba[6] & 0xE0 ##Don't care about hops, and we already know it's standard
        cmd1 = ba[7]
        cmd2 = ba[8]
        if dst == bytearray([0x0,0x0,0x0]):
            return #Don't care about these broadcasts for now, i guess
        elif dst == MODEM: ##Command is for me!
            logging.debug(binascii.hexlify(ba))
            if msgType & 0x20: ##ACK
                logging.debug("ACK Message")
            if not msgType & 0xc0:
                logging.debug("Direct Message")
                resp = self.standardDirectCommandParse(cmd1,cmd2)
                if type(resp) == dict:
                    self.devices[devname].update_state(**resp)
                else:
                    logging.debug("Different response was " + type(resp))
                logging.info(devname + " turned to " + str(self.devices[devname]._on))
                if not msgType:
                    logging.debug("New Command")
            else:
                if msgType & 0x80: ##Broadcast
                    logging.debug("Broadcast Message")
                if msgType & 0x40: ##ALLLink
                    logging.debug("Link Message")
                    ##really, more of a command... would need to figure out how to state machine or something
                    self.devices[devname]["state"] = self.standardDirectCommandParse(cmd1,cmd2)
                    logging.info("devname turned to " + str(self.devices[devname]._on))
    def standardDirectCommandParse(self, cmd1, cmd2):
        level = 0x00
        if cmd1 == 0x11 or cmd1 == 0x12: #On and FastOn
            level = cmd2
            return {"on": True, "level": int(level)}
        elif cmd1 == 0x13 or cmd1 == 0x14: #off and FastOff
            level = 0x00
            return {"on": False, "level": int(level)}
        elif cmd1 == 0x15: ##brighten one setp
            pass
        elif cmd1 == 0x16: ##dim one step
            pass
        elif cmd1 == 0x19: ##status
            pass
        elif cmd1 == 0x22: ##load changed off
            level = 0x00
        elif cmd1 == 0x23: ##load change on
            level = 0xFF

##For properties or something
    def dimmers(self):
        lightarray = []
        for key in self.devices:
            if self.devices[key]._category == "01":
                lightarray.append(self.devices[key])
        return lightarray
    def switchLights(self):
        lightarray = []
        for key in self.devices:
            if self.devices[key]._category ==  "02":
                lightarray.append(self.devices[key])
        return lightarray

                

            

            



def sendToDev(ser, barray, responseSizeArray, lock):
    with lock:
        logging.debug("Got lock")
        ser.write(barray)
        ackline = ser.read(len(barray) + 1).strip()
        test = barray
        test.append(0x06)
        if ackline == test:
            logging.debug("Got ack'd")
        else:
            logging.info("NO ACK?!?!")
            logging.info(binascii.hexlify(barray))
            logging.info(binascii.hexlify(ackline))
        responses = []
        for i in responseSizeArray:
            try:
                respline = ser.read(i).strip()
                responses.append(respline)
            except:
                logging.error("Failed with barray")
                logging.error(binascii.hexlify(barray))
                logging.error("With responses:")
                for item in responses:
                    logging.error(binascii.hexlify(item))
                return
            i+=1
        return responses

def getDeviceID(ser, dev, lock):
    device = dev["hexaddr"]
    if len(device) != 6:
        logging.error("Wrong length device")
        dev["category"]= "FF"
        dev["subcategory"]="FF"
        return dev
    idreq = bytearray([0x02,0x62])
    idreq.extend(bytearray.fromhex(device)) ##Add the device's hex address
    idreq.extend([0x0F,0x10,0x00])
    responses=sendToDev(ser, idreq, [11, 11], lock)
    for item in responses:
        print("For device "+ device + " we got: " + str(binascii.hexlify(item)))
    try:
        response = responses[1]
        devCat = "{:02x}".format(response[5])
        devSubcat = "{:02x}".format(response[6])
        devRev = "{:02x}".format(response[7])
        devHardRev = "{:02x}".format(response[10])
        dev["category"]=devCat
        dev["subcategory"]=devSubcat
        return dev
    except:
        logging.error("failed with responses")
        for item in responses:
            logging.error(binascii.hexlify(item))
        dev["category"]= "FF"
        dev["subcategory"]="FF"
        return dev
        

def getLinks(ser,lock):
    devices = {}
    devlist = []
    with lock:
        logging.error("Got lock")
        message = bytearray([0x02,0x69])
        ser.write(message)
        string = ser.read(3).strip()
        logging.debug("First real read")
        if string != bytearray([0x02,0x69,0x06]):
            logging.error(binascii.hexlify(string))
        string = ser.read(10)
        nohead = ''.join('{:02x}'.format(x) for x in string[2:])
        #a2042e89fd013a48
        linkflag = nohead[:4]
        devname = nohead[4:10]
        linkdata = nohead[10:]
        device = {"hexaddr" : devname, "linkdata": linkdata, "linkflag": linkflag}
        devlist.append(device)
        devices[devname] = device

        while True:
            message = bytearray([0x02,0x6A])
            ser.write(message)
            string = ser.read(3).strip()
            mend = bytearray([0x02,0x6A,0x15])
            if string != mend:
                string = ser.read(10).strip()
                nohead = ''.join('{:02x}'.format(x) for x in string[2:])
                linkflag = nohead[:4]
                devname = nohead[4:10]
                linkdata = nohead[10:]
                device = {"hexaddr" : devname, "linkdata": linkdata, "linkflag": linkflag}
                devlist.append(device)
                devices[devname] = device
            else:
                return devices
def setModemMonitor(ser, tf, lock):
    with lock:
        if tf:
            ser.reset_input_buffer()
            ser.write(bytearray([0x02,0x6B,0x40]))
            string = ser.read(4).strip()
            if string != bytearray([0x02,0x6B,0x40,0x06]):
                logging.error("ERROR SETTING MODEM CONFIG")
                logging.error(binascii.hexlify(string))
        else:
            ser.reset_input_buffer()
            ser.write(bytearray([0x02,0x6B,0x00]))
            string = ser.read(4).strip()
            if string != bytearray([0x02,0x6B,0x00,0x06]):
                logging.error("ERROR SETTING MODEM CONFIG")
                logging.error(binascii.hexlify(string))
