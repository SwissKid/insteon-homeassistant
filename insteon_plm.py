import logging
import testlib as insteon
import queue, threading, json, os, serial

# Import the device class from the component that you want to support
from homeassistant.components.light import ATTR_BRIGHTNESS, Light
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, STATE_ON, STATE_OFF


# Home Assistant depends on 3rd party packages for API specific code.
REQUIREMENTS = ['pyserial']

_LOGGER = logging.getLogger(__name__)
INSTEON_CONFIG_FILE = 'insteon.conf'


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error('Saving config file failed: %s', error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error('Reading config file failed: %s', error)
                # This won't work yet
                return False
        else:
            return {}



def setup_platform(hass, config, add_devices, discovery_info=None):
    """Initialize Awesome Light platform."""
    prelist = config_from_file(hass.config.path(INSTEON_CONFIG_FILE))


    # Validate passed in config
    host = config.get(CONF_HOST, "test")
    username = config.get(CONF_USERNAME, "test")
    password = config.get(CONF_PASSWORD, "test")

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
    devlist = {}
    devices = {}
    for item in testlist:
        if item in prelist:
            devlist[item] = prelist[item]
            devices[item] = insteon.Device(q, ser, lock, **prelist[item])
        else:
            response = insteon.getDeviceID(ser,testlist[item], lock)
            devlist[item] = response
            devices[item] = insteon.Device(q, ser, lock, **response)
    with open("test_devices.json", "w") as outfile:
        json.dump(devlist, outfile)
        outfile.close()
    logging.debug(devlist)
    logging.debug(devices)

    insteon.setModemMonitor(ser,True,lock)
    t = insteon.serWatcher(ser,lock, devices, q)
    t.start()
    

    if not config_from_file(
            hass.config.path(INSTEON_CONFIG_FILE),
            devlist):
        _LOGGER.error('failed to save config file')
    # Add devices
    add_devices(InsteonDimmer(light) for light in t.dimmers())
    add_devices(InsteonSwitch(light) for light in t.switchLights())

class InsteonSwitch(Light):
    """Represents an AwesomeLight in Home Assistant."""

    def __init__(self, light):
        """Initialize an AwesomeLight."""
        self._device = light

    @property
    def should_poll(self):
        return False #polling isn't doing anything for now

    @property
    def name(self):
        """Return the display name of this light"""
        if self._device.name != "":
            return self._device.name
        else:
            return self._device.hexid

    @property
    def is_on(self):
        """If light is on."""
        return self._device._on
    
    @property
    def state(self):
        if self._device._on:
            return STATE_ON
        else:
            return STATE_OFF

    #@property
    def turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        self._device.turn_on()
        self.update_ha_state()

    #@property
    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._device.turn_off()
        self.update_ha_state()

    @property
    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assitant.
        """
        self._device.update()

class InsteonDimmer(InsteonSwitch):
    """Represents an AwesomeLight in Home Assistant."""

    def __init__(self, light):
        """Initialize an AwesomeLight."""
        self._device = light

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255).

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._device._brightness

    #@property
    def turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        self._device._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._device.turn_on(self._device._brightness)
        self.update_ha_state()


    @property
    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assitant.
        """
        self._device.update()


