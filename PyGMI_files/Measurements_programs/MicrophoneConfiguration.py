import logging
import math
import numpy
import pprint
import threading
import time
from Tkinter import *
import tkMessageBox

#from microphone_uncertainties import attenuator_uncertainty


class takeInput(object):
    """Utility class to show popup and get user input string.
    """
    def __init__(self,requestMessage):
        self.root = Tk()
        self.string = ''
        self.frame = Frame(self.root)
        self.frame.pack()        
        self.acceptInput(requestMessage)

    def acceptInput(self,requestMessage):
        r = self.frame

        k = Label(r,text=requestMessage)
        k.pack(side='left')
        self.e = Entry(r,text='Name')
        self.e.pack(side='left')
        self.e.focus_set()
        b = Button(r,text='okay',command=self.gettext)
        b.pack(side='right')

    def gettext(self):
        self.string = self.e.get()
        self.root.withdraw()
        self.root.destroy()
        self.root.quit()

    def getString(self):
        return self.string

    def waitForInput(self):
        self.root.mainloop()

def getText(requestMessage):
    msgBox = takeInput(requestMessage)
    #loop until the user makes a decision and the window is destroyed
    msgBox.waitForInput()
    msg = msgBox.getString()   
    return msg

def wait(msg):
    """Wait until any key is pressed.
    """
    Tk().wm_withdraw() #to hide the main window
    tkMessageBox.showinfo("Calibration",msg)

######create a separate thread to run the measurements without freezing the front panel######
class Script(threading.Thread):
            
    def __init__(self,mainapp,frontpanel,data_queue,stop_flag,GPIB_bus_lock,**kwargs):
        #nothing to modify here
        threading.Thread.__init__(self,**kwargs)
        self.mainapp=mainapp
        self.frontpanel=frontpanel
        self.data_queue=data_queue
        self.stop_flag=stop_flag
        self.GPIB_bus_lock=GPIB_bus_lock
        
    def run(self):
        m=self.mainapp              #a shortcut to the main app, especially the instruments
        f=self.frontpanel           #a shortcut to frontpanel values
        reserved_bus_access=self.GPIB_bus_lock     #a lock that reserves the access to the GPIB bus
                
        logging.info("init all instruments")
        self.keithley2001 = m.instr_1   # GBIP0::16
        self.racaldana = m.instr_2      # GBIP0::14
        self.agilent3350A = m.instr_3   # GBIP0::20
        self.kh6880A = m.instr_4        # GBIP0::1
        self.bk2636 = m.instr_5         # GBIP0::4
        self.dpi141 = m.instr_6         # GBIP0::2
        self.el100 = m.instr_7          # GBIP0::3
                
        # debugging script
        # agilent on
        # kh on
        # racal on
        # keithley 2001 must read channel 3 AC, value 1 V
        #self.agilent3350A.turn_on()
        #v_test = self.keithley2001.scan_channel(3, "VOLT:AC")
        #print(v_test)    
        #sys.exit(0)
           
        SPL_standard = []
        SPL_device = []
         
        t1 = float(getText("Initial temperature (oC)").strip())
        rh1 = float(getText("Initial humidity (%)").strip())
        p1 = self.dpi141.read() 
        vpol1 = self.keithley2001.scan_channel(4, "VOLT:DC")[0]
        self.check_temperature(t1)
        self.check_humidity(rh1)
        self.check_pressure(p1)
        self.check_vpol(vpol1)
        
        self.calibrator_nominalevel = int(getText("Calibrator Nominal Level (94, 104 or 114dB)").strip())
        self.micsensitivity = float(getText("Microphone Sensitivity (check certificate, e.g. -26.49)").strip())
        self.bk2636.decide_set_gain(self.calibrator_nominalevel, self.micsensitivity)
        
        for i in range(5):           
            self.stop_switch_instrument("Reference Standard") 
            res = self.measure_SPL("Reference Standard")
            SPL_standard.append(res)
            # TODO enable again
            #self.stop_switch_instrument("Customer Device")
            #res = self.measure_SPL("Customer Device") 
            SPL_device.append(res)
            # TODO remove this 
            break               
        
        # final env conditions
        t2 = t1 # TODO float(getText("Final temperature (oC)").strip())
        rh2 = rh1 # TODO float(getText("Final humidity (%)").strip())
        p2 = self.dpi141.read()
        vpol2 = self.keithley2001.scan_channel(4, "VOLT:DC")[0]
        
        self.check_temperature(t2)
        self.check_humidity(rh2)
        self.check_pressure(p2)
        self.check_vpol(vpol2)
        
        env = dict(temperature=(t1+t2)/2.0,
                   relative_humidity=(rh1+rh2)/2.0,
                   pressure=(p1+p2)/2.0,
                   polarising_voltage=(vpol1+vpol2)/2.0)
        
        standard_uncertainty = self.calculate_uncertainties(SPL_standard)
        device_uncertainty = self.calculate_uncertainties(SPL_device)       
                
        self.print_results(env, SPL_standard, SPL_device, standard_uncertainty,
                           device_uncertainty)               
    
    def measure_SPL(self, device_name):
        """"Big process that is repeated 5 times for working standard
        and customer device. The final output is a dict with all measurements.
        """               
        self.agilent3350A.turn_off()
       
        # check Keithley2001 DC & CURR stability/fluctuation. 
        dc_volt = self.keithley2001.scan_channel(5, "VOLT:DC", times=2, interval=0.99)  # TODO set times=20
        self._check_stability(dc_volt)
        vmic = sum(dc_volt) / len(dc_volt)
        # MA o/p (V) is vmic
        
        # Read total harmonic distortion from Krohn Hite.
        kh_list1 = self.kh6880A.read(times=10, delay=1.99)
        kh_avg1 = sum(kh_list1) / len(kh_list1)
        wait("Stop %s, press any key to continue..." % device_name)
                
        # start agilent3350A, send 6V peak to peak, freq 1000Hz, SINE waveform.
        # the attenuator is adjusted until the voltage matches (to 0.005 db) the
        # output of the calibrator (VmicAmpl(ch5) - VinsertAmpl(ch5))           
        self.agilent3350A.turn_on()
        # Vdev = Vmic
        # Vsys = Vins
        
        # atten#=100.0# - micsensitivity# - nomlevel#
        # micsensivity input variable by user (certificate). e.g. value -26.49
        # nomlevel = 94
        atten = 100.0 - (self.micsensitivity) - 94
        good_consec = 0
        vins = 0.0
        while good_consec < 2:
            attenuator_str = "%05.2f" % atten
            self.el100.set(attenuator_str)
            vins = self.keithley2001.scan_channel(5, "VOLT:DC")[0]
            # MA o/p (V) is vins
                        
            # convert to dB
            attenerror = abs(20.0 * math.log10(vmic / vins))
            if attenerror <= 0.005:
                good_consec += 1
                print("SUCCESS", attenerror)
            else:
                print("ERROR", attenerror)
                atten -= attenerror
                time.sleep(5)
        self.agilent3350A.turn_off()
        
        # measure Vins voltage (ch3) keythley
        dc_volt = self.keithley2001.scan_channel(3, "VOLT:AC", times=2, interval=0.99)  # TODO set times=20
        vins_source3 = abs(sum(dc_volt) / len(dc_volt)) # TODO this was negative!!
        
        rd_avg = self.racaldana.read_average(times=2, delay=1.99)   # TODO set times=20
        logging.info("Racal Dana read %g", rd_avg)
        # Racal Dana values must be around 1000 Hz +-10%
        # TODO fix
        #if rd_avg < 900.0 or rd_avg > 1100.0:
        #    wait("Critical Error! Racal Dana value outside range: %g. Terminating program." % rd_avg)
        #    sys.exit(0)
            
        # distortion value (kh6880A)
        kh_list2 = self.kh6880A.read(times=10, delay=1.99)      
        kh_avg2 = sum(kh_list2) / len(kh_list2)
        
        # TODO ? Use kh_list1 and kh_list2 ?? Cannot understand what the original code does.
        arr = numpy.array(kh_list2)
        thd = numpy.std(arr)
        
        SPL = self.uncorrected_sound_pressure_level(vins_source3, atten,
                                                    self.micsensitivity) 
        krohn_hite = (kh_avg1 + kh_avg2)/2.0
        # measurements
        return dict(
            attenuation=atten,
            thd=thd,
            krohn_hite=krohn_hite,
            racal_dana=rd_avg,
            SPL=SPL,
            Vmic=vmic,      # MA_op first
            Vins=vins,      # MA_op second
            IV=vins_source3,  # THIS IS IV
            p_v_corr=0  # TODO ?
        )
        
    def uncorrected_sound_pressure_level(self, Vins, A, M):
        """SPL calculation. Params:
        Vins: measured insert voltage
        A: attenuation (dB)
        M: sensitivity (dB re 1 VPa-1)
        Output: SPL
        """
        SPL = (20.0*math.log10(Vins)) - (20.0 * math.log10(2.0*math.pow(10, -5))) -A - M
        return round(SPL, 3)

    
    def stop_switch_instrument(self, device):
        wait("Please connect and turn on the %s." % device)
    
    def _keithley_wait_until_dc_voltage(self, limit=0.5):
        """"Read DC voltage from keithley2001 until value > 0.5V.
        If not, sleep for 1 sec and retry.
        """      
        self.keithley2001.set_measurement_mode("DC")
        while(True):
            dc_voltage = self.keithley2001.query_voltage_average()
            if dc_voltage > 0.5:
                break
            time.sleep(1)
    
    def _check_stability(self, values):
        """Input is list of floats. If last/first value < 0.7, faulty reading.
        Exit with an error"""
        if values[-1] / values[0] < 0.7:
            logging.error("Fatal problem with measurement stability.")
            logging.error(values)
            sys.exit(0)
        # TODO return and save stability (fluctuation)
            
    def check_temperature(self, temp):
        if not 20.0 <= temp <= 26:
            msg = "Temperature %g outside preferred range of 23+-3 oC." % temp
            logging.error(msg)
            wait(msg)
                        
    def check_humidity(self, rh):
        if not 30.0 <= rh <= 70.0:
            msg = "Humidity %g outside preferred range of 50+-20%." % rh
            logging.error(msg)
            wait(msg)
    
    def check_pressure(self, pre):
        if not 1003.0 <= pre <= 1023.0:
            msg = "Pressure %g outside preferred range of 1013+-10."% pre
            logging.error(msg)
            wait(msg)
    
    def check_vpol(self, v):
        if not 198.0 <= v <= 202.0:
            msg = "Polirization V %g outside preferred range of 200+-2V." % v
            logging.error(msg)
            wait(msg)
            
    def calculate_fluctuation(self, v_list):
        """Calculate fluctuation for a list of values.
        """
        mean_val = sum(v_list) / len(v_list)
        max_val = max(v_list)
        min_val = min(v_list)
        highest_fluctuation = 20 * math.log10(max_val / mean_val)
        lowest_fluctuation = 20 * math.log10(min_val/ mean_val)
        if abs(highest_fluctuation) > abs(lowest_fluctuation):
            return highest_fluctuation
        else:
            return lowest_fluctuation
        
    def calculate_uncertainties(self, measurements):
        # TODO get from conf file
        Vinsert = 1.0005    # get from Voltmeter certificate uncertainty
        Verror = 1.0003     # get from voltmeter certificate uncertainty
        IVu = self.voltmeter_uncertainty(1.0005)
        IVe = self.voltmeter_error(1.0003)
        
        # based on the attenuation setting that was calculated in the calibration
        avg_attenuation = sum([row['attenuation'] for row in measurements]) / len(measurements)
        Au = self.attenuator_uncertainty(avg_attenuation)
        Ae = self.attenuator_error(avg_attenuation)
        
        Mu = 0.01    # ref microphone sensitivity from certificate
        Mp = 0.038   # correction to ref microphone sensitivity for static pressure from TABLE page 24 of 42.
        
        # we use only mic models 4180 or 4190
        # For 4180, we said:
        #   31.5 - 2000     0.007
        #   4000            0.012
        #   8000            0.026
        #  12500            0.047
        #  16000            0.042
        #
        # mic model 4190
        Mt = 0.050   # correction to ref microphone sensitivity for ambient temperature
        
        MM = 0.005    # error in matching the device's output voltage and the system voltage
        Kpv = 0.01    # correction of polarising voltage
        Kp = 0.02     # correction of static pressure. Fixed value for mics 4180 & 4190.
        Kmv = 0.02    # correction of differing volume of microphones. Fixed value for mics 4180 & 4190.
        SPLr = 0.005  # resolution of result
        
        SPL_avg = sum(item['SPL'] for item in measurements) / len(measurements)
        
        u_SPL = IVu + IVe - 20*math.log10(0.00002) - Au + Ae - Mu + Mp + Mt +\
                MM + Kpv + Kp + Kmv + SPLr 
        
        u_total = self.combined_uncertainty(IVu, IVe, Au, Ae, Mu, Mp, Mt, MM, Kpv, Kp, Kmv, SPLr, SPL_avg)
               
        spls = numpy.array([item['SPL'] for item in measurements])
        u_type_A = numpy.std(spls) 
        
        frequencies = numpy.array([item['racal_dana'] for item in measurements])
        u_frequency = numpy.std(frequencies) * 2.0
        
        return dict(
            u_total=u_total * 2.0,
            u_thd=Au * 2.0,
            u_SPL=u_SPL,
            u_type_A=u_type_A,
            u_frequency=u_frequency
            )
     
    def combined_uncertainty(self, IVu, IVe, Au, Ae, Mu, Mp, Mt, MM, Kpv, Kp, Kmv, SPLr, spl):
        sqrt3 = math.sqrt(3)

        u_IVu = math.pow(IVu / 2.0, 2)
        u_IVe = math.pow(IVe / sqrt3, 2)
        u_Au = math.pow(Au / 2.0, 2)
        u_Ae = math.pow(Ae / math.sqrt(3), 2)
        u_Mu = math.pow(Mu / 2.0, 2)
        u_Mp = math.pow(Mp / sqrt3, 2)
        u_Mt = math.pow(Mt / sqrt3, 2)
        u_MM = math.pow(MM / sqrt3, 2)
        u_Kpv = math.pow(Kpv / sqrt3, 2)
        u_Kp = math.pow(Kp / sqrt3, 2)
        u_Kmv = math.pow(Kmv / sqrt3, 2)
        u_SPLr = math.pow(SPLr / sqrt3, 2)       
    
        total = u_IVu + u_IVe + u_Au + u_Ae + u_Mu + u_Mp + u_Mt + u_MM + u_Kpv +\
                u_Kp + u_Kmv + u_SPLr
        return round(math.sqrt(total), 3)   
                
    
    def voltmeter_uncertainty(self, val):
        """Keithley2001
        Get value from Voltmeter certificate uncertainty.
        """
        return 20 * math.log10(val)

    def voltmeter_error(self, val):
        """Keithley2001
        """
        return self.voltmeter_uncertainty(val)

    def attenuator_uncertainty(self, value):
        """input: MSD (tens) of attenuator setting value (first digit)
        output: Au (dB) (0.01 - 0.06)
        """
        attenuator_str = "%05.2f" % value
        msd = int(attenuator_str[0])
        if msd == 0:
            return 0.01
        elif msd == 1:
            return 0.02
        elif msd == 2:
            return 0.03
        elif msd == 3:
            return 0.04
        elif msd == 4:
            return 0.05
        elif msd == 5:
            return 0.06
    
    def attenuator_error(self, value):
        """Error in attenuator reading (dB) for different frequency ranges.       
        frequency = Agilent frequency = 1000 (ALWAYS)
        table 15.5, page 23 of 42, only the second column applies (250Hz to 2kHz)
        
        0.004 uncertainty is STANDARD in all cases (LSD uncertainty).
        We add to this according to MSD (first digit of attenuator value)
        """
        attenuator_str = "%05.2f" % value
        msd = int(attenuator_str[0])
        if msd == 0:
            return 0.004
        elif msd == 1 or msd == 2:
            return 0.004 + 0.004
        elif msd == 3:
            return 0.005 + 0.004
        elif msd == 4 or msd == 5:
            return 0.005 + 0.004
        elif msd == 6:
            return 0.006 + 0.004
    
    def microphone_est_maximum_error(self, mic_type, freq, spr, Mp):
        """mic_type: Microphone type
        freq: Frequency range (Hz)
        spr: Static pressure range (kPa)
        Mp: (dB)
        """
        return 0.01
    
    def coverage_factor(self, niterns, urfreq, ufreq, k_necessary):
        return 0.1

    def print_results(self, env, SPL_standard, SPL_device, standard_u, device_u):       
        header = "Freq(Hz)    MA o/p (V)    MA o/p (V)    IV (V)    Atten (dB)    P+V Corrn (dB), S.P.L. (dB)    THD (%)"
        resline ="%.1f        %.2f          %.2f          %.2f      %.2f          %.2f            %.2f           %.2f"
        
        def _print_instrument(header, resline, data, data_u):
            print(header)
            for row in data: 
                print(resline % (row['racal_dana'], row['Vmic'], row['Vins'], row['IV'], row['attenuation'],
                      row['p_v_corr'], row['SPL'], row['thd']))
            mean_freq = sum(row['racal_dana'] for row in data) / len(data)
            mean_SPL = sum(row['SPL'] for row in data) / len(data)
            mean_thd = sum(row['thd'] for row in data) / len(data)
            # Racal Dana Freq + Uncertainty, Krohn Hite Freq = Uncertainty
            print("Mean Freq = %.2f Hz, Freq unc = %.2f Hz (k=2.00) Mean dist=%.2f%% Dist unc=%.2f%% (k=2.00)" %
                  (mean_freq, data_u['u_frequency'], mean_thd, data_u['u_thd']))
            print("Mean S.P.L. = %.2f" % mean_SPL)
            print("Type A unc = %.3f dB Total unc = %.3f dB" % (
                data_u['u_type_A'], data_u['u_total']))
            
        print("Pressure %.2f Temperature %.2f Relative Humidity %.2f" % (
              env['pressure'], env['temperature'], env['relative_humidity']))
        print("Polarising Voltage %.2f" % env['polarising_voltage'])
        
        print("--- Working Standard Results ---")
        _print_instrument(header, resline, SPL_standard, standard_u)
        print("--- Customer Device Results ---")
        _print_instrument(header, resline, SPL_device, device_u)