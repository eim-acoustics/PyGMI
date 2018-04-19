# -*- coding: utf-8 -*-
import logging
import sys
import time
import visa
from PyGMI_files import measurements_done_alert

# set logging output to stdout
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

#TODO channel option

#TODO filter (gia to AC mono)
# οταν μετράς σε χαμηλές συχνότητες να κόβει κάποιες πάνω από ένα όριο
# FILTER ON / OFF

def parse_float(input):
    """Utility method to parse instrument output and return float value.
    """
    return float(input.split(",")[0].replace("NVDC", "").replace("NVAC", ""))

class Connect_Instrument():
    """Potential values are: AC, DC.
    """
    instr_mode = 'AC'
    
    def __init__(self, VISA_address="GPIB0::16"):
        self.io = visa.instrument(VISA_address)
        logging.info("Init instrument %s", self.io.ask("*IDN?"))
        
    def initialize(self):
        """commands executed when the instrument is initialized"""
        self.io.write("*CLS")
        logging.info("CLS* => Clear all registers and logs")
        self.set_measurement_mode("AC")
        self.open_channel(2)
        print(self.query_voltage_average())

    def reset_autozero(self, duration=1):
        self.io.write("*CLS")
        self.io.write(':SYSTem:AZERo:STATe ON')
        self.io.write(':syst:faz ON')
        time.sleep(duration)
        self.io.write(':syst:faz off')
        self.io.write(':SYSTem:AZERo:STATe OFF')
        logging.info("reset autozero")

    def list_channels(self):
        # not used anywhere
        internal = self.io.ask(":ROUT:SCAN:INT?")
        external = self.io.ask(":ROUT:SCAN:EXT?")
        
    def scan_channel(self, channel, measurement, times=1, interval=0.1):
        """Scan channel for requirement measurement and return list of float
        values.
        :param channel: integer, 1 to 10
        :param measurement: string, e.g. 'volt:dc'
        :param times: integer, how many times it will measure
        :param delay: float, delay between each measurement
        """
        logging.info("SCAN CHANNEL %d measurement %s times %d interval %g",
                     channel, measurement, times, interval)
        self.io.write(":rout:SCAN:LSEL INT")
        self.io.write(":rout:CLOSE (@%d)" % channel)
        self.io.write(":rout:open (@%d)" % channel) 
        self.io.write(":rout:scan:int:func (@%d), '%s'" % (channel, measurement))
        self.io.write(":rout:scan:int (@%d)" % channel)
        out = []
        for i in range(0, times):
            out.append(round(parse_float(self.io.ask(":READ?")), 5))
            time.sleep(interval)
        self.io.write(":rout:CLOSE (@%d)" % channel)
        return out

    def setup_single_shot(self,verbose=False):
        """
        print "configuring Keithley2182A for continuously taking low speed single shot readings"
        lnanoV=[':syst:pres', # 2182 - System preset defaults.
                ':CONF:VOLT',
                ':INIT:CONT OFF']
        for txt in lnanoV:
            if verbose:
                print txt
            self.io.write(txt)
        """

    def setup_single_shot_Tlink(self,verbose=False):
        """
        print "configuring Keithley2182A for a single shot with trigger link cable"
        lnanoV=[':syst:pres', # 2182 - System preset defaults.
                ':CONF:VOLT',
                ':SENSe:VOLTage:DC:RANGe 0.0001',
                ':SENSe:VOLTage:DC:LPASs OFF',
                ':SENSe:VOLTage:DC:DFILter OFF',
                ':TRIG:DEL:AUTO OFF',
                ':trig:del 0',
                ':SENS:VOLT:NPLC 0.1',
                ':DISPlay:ENABle ON',
                #':sens:volt:delta on',
                ':syst:faz off',
                ':SYSTem:AZERo:STATe OFF',
                ':trig:sour ext',
                #':trac:poin '+buff_pts,
                ':SYSTem:LSYNc:STATe ON',
                #':trac:feed:cont next',
                ':trig:coun inf',
                ':SAMP:COUN 1',
                ':INIT']

        for txt in lnanoV:
            if verbose:
                print txt
            self.io.write(txt)
        time.sleep(1) #init needs at least one second to complete
        """
        
    def setup_sensitivity_combobox(self,comboBox):
        comboBox.clear()        
        comboBox.addItems(self.sensitivity)                

    def query_unit_Id(self):
        return self.io.ask("*IDN?")

    def reset_and_query_voltage(self):
        """This query is much slower than a “:READ?” or “:FETCh?” query because it has to
reconfigure the instrument each time it is sent. It will reset the NPLC, autoranging, and
averaging to default settings."""
        
        # output format like:
        # BEFORE -38.3204E-03NVDC,+73597.273513SECS,+39170RDNG#,00EXTCHAN
        
        # AFTER   -0.0211E-03NVDC,+74476.652779SECS,+39174RDNG#,00EXTCHAN

        #return float(self.io.ask(":MEAS:VOLT?"))
        return self.io.ask(":MEAS:VOLT?")

##:READ? :This command performs three actions. It will reset the trigger model to the idle layer
##(equivalent to the :ABORt command), take the trigger model out of idle (equivalent to the :INIT
##command), and return a reading (equivalent to a “FETCh?” query). This command will always
##return a new reading, since aborting the trigger model will invalidate any old readings and
##trigger a new one. This query will “wait” for a new reading to become available before the
##instrument sends a result back.
##    This command won’t work if the trigger source is set for BUS or EXTERNAL. This will
##cause a –214, “Trigger deadlock” error. Under this condition, one should use a “:FETCh?” query
##or a “:DATA:FRESh?” query (see page H-4). If the trigger model is continuously initiating
##(:INIT:CONT ON), sending this query may cause a –213, “Init ignored” error, but will still give
##a new reading.
    def query_voltage(self):
        tmp = self.io.ask(":READ?")
        voltage = tmp.split(",")[0]
        return float(voltage.replace("NVAC", ""))
    
    def query_latest_reading(self):
        """This command does not trigger a measurement. The command simply requests the last
available reading. Note that this command can repeatedly return the same reading."""
        return float(self.io.ask(':FETCh?'))

    def query_latest_fresh_reading(self):
        """This query is similar to the “:FETCh?” in that it returns the latest reading from the instrument,
but has the advantage of making sure that it does not return the same reading twice."""
        return float(self.io.ask(':sens:data:fresh?'))

    def query_current_source_amplitude(self):
        """Make 10 measurements of current and return average.
        """        
        if self.instr_mode == "DC":
            self.io.write(":curr:dc:nplc 10")
        elif self.instr_mode == "AC":
            self.io.write(":curr:ac:nplc 10")
        result = self.io.ask(":read?")
        logging.info(result)
        if result:
            return float(result.split(",")[0].replace("NVDC", "").replace("NVAC", ""))
        else:
            return 0.0

    def query_voltage_average(self):
        return self.query_voltage_compliance()

    def query_voltage_compliance(self):
        """Make 10 measurements of voltage and return average.
        """
        if self.instr_mode == "DC":
            self.io.write(":volt:dc:nplc 10")
        elif self.instr_mode == "AC":
            self.io.write(":volt:ac:nplc 10")
        result = self.io.ask(":read?")
        logging.info(result)
        if result:
            return float(result.split(",")[0].replace("NVDC", "").replace("NVAC", ""))
        else:
            return 0.0
    
    def open_channel(self, channel):
        """Set channel to use for measurement.
        """
        self.io.write(":ROUT:OPEN:SCAN:INT:FUNC 5 VOLT:DC")
    
    def close_channel(self, channel):
        self.io.write(":ROUT:CLOS %d" % channel)
    
    def set_measurement_mode(self, mode):
        """Value can be: AC, DC.
        """
        self.instr_mode = mode
        if mode == "DC":
            self.io.write(":conf:volt:dc")
        elif mode == "AC":
            self.io.write(":conf:volt:ac")
        logging.info("Set measurement mode to %s", mode)
        
    def set_voltage_compliance(self, value):
        print("TODO SET voltage_compliance", value)
    
    def set_current_source_amplitude(self, value):
        print("TODO SET current_source_amplitude", value)
    
#:MEASure:<function>?
#Parameters
#<function> = VOLTage[:DC] Voltage
#TEMPerature Temperature
#Description
#This command combines all of the other signal oriented measurement commands to perform
#a “one-shot” measurement and acquire the reading.
#When this command is sent, the following commands execute in the order that they are
#presented.
#:ABORt
#:CONFigure:<function>
#:READ?
#When :ABORt is executed, the instrument goes into the idle state if continuous initiation is
#disabled. If continuous initiation is enabled, the operation re-starts at the beginning of the
#Trigger Model.
#When :CONFigure is executed, the instrument goes into a “one-shot” measurement mode.
#See :CONFigure for more details.
#When :READ? is executed, its operations will then be performed. In general, another
#:ABORt is performed, then an :INITiate, and finally a :FETCh? to acquire the reading. See
#“:READ?” for more details.

    def select_channel(self,chan):
        self.io.write(':SENS:CHAN '+str(chan))

#Select channel to measure; 0, 1 or 2 (0 = internal temperature sensor).
    
#:ROUTe:TERMinals <name> Select front or rear panel in/out jacks
#Parameters <name> = FRONt Front panel in/out jacks
#REAR Rear panel in/out jacks
#Query :TERMinals? Query state of front/rear switch setting

    def current_source_range(self,RANGe):
        self.io.write(':SOUR:CURR:RANG '+str(RANGe))

    def voltage_source_range(self,RANGe):
        self.io.write(':SOUR:CURR:RANG '+str(RANGe))

    def set_integration_rate(self,NPLC):
        self.io.write(':SENS:VOLT:NPLC '+str(NPLC))

    def set_sensitivity(self,RANGE):
        self.io.write(':SENS:VOLT:RANG '+str(RANGE))
        
    def enable_filter(self):
        if self.instr_mode == "DC":
            self.io.write(":SENS:VOLT:DC:AVER:STAT 1")
        elif self.instr_mode == "AC":
            self.io.write(":SENS:VOLT:AC:AVER:STAT 1")
        logging.info("ENABLE FILTER")
            
    def disable_filter(self):
        if self.instr_mode == "DC":
            self.io.write(":SENS:VOLT:DC:AVER:STAT 0")
        elif self.instr_mode == "AC":
            self.io.write(":SENS:VOLT:AC:AVER:STAT 0")
        logging.info("DISABLE FILTER")
        