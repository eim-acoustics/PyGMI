import logging 
import threading
import time
from Tkinter import *
from tkFileDialog import askopenfilename
import tkMessageBox
import winsound
import yaml


class Standard61672(object):
    def frequency_weighting_tolerance_limits(self, frequency_weighting,
                                             nominal_frequency, ref_spl,
                                             measured_spl, windshiled_correction,
                                             case_correction):
        """ISO61672-1 IEC:2002, Table 2, Page 33.
        Frequency_weighting = 'A', 'C' or 'Z'
        NOTE that there is a standard uncertainty budget = 0.21
        The final result will be 1, 2 or 3 (fail)
        """
        table_freq_weightings = {
            1000.0: {"A": 0.0, "C": 0.0, "Z": 0.0},
            2000.0: {"A": 1.2, "C": -0.2, "Z": 0.0},
            4000.0: {"A": 1.0, "C": -0.8, "Z": 0.0},
            8000.0: {"A": -1.1, "C": -3.0, "Z": 0.0},
           12500.0: {"A": -4.3, "C": -6.2, "Z": 0.0},
           16000.0: {"A": -6.6, "C": -8.5, "Z": 0.0},
              31.5: {"A": -39.4, "C": -3.0, "Z": 0.0},
              63.0: {"A": -26.2, "C": -0.8, "Z": 0.0},
             125.0: {"A": -16.1, "C": -0.2, "Z": 0.0},
             250.0: {"A": -8.6, "C": 0.0, "Z": 0.0},
             500.0: {"A": -3.2, "C": 0.0, "Z": 0.0}
        }
        tolerance_limits = {
            1000.0: {1: {"min":-1.1, "max": 1.1}, 2: {"min": -1.4, "max": 1.4}},
            2000.0: {1: {"min":-1.6, "max": 1.6}, 2: {"min": -2.6, "max": 2.6}},
            4000.0: {1: {"min":-1.6, "max": 1.6}, 2: {"min": -3.6, "max": 3.6}},
            8000.0: {1: {"min":-3.1, "max": 2.1}, 2: {"min": -5.6, "max": 5.6}},
           12500.0: {1: {"min":-6.0, "max": 3.0}, 2: {"min": -1000.0, "max": 6.0}},
           16000.0: {1: {"min":-17.0, "max": 3.5}, 2: {"min": -1000.0, "max": 6.0}},
              31.5: {1: {"min":-2.0, "max": 2.0}, 2: {"min": -3.5, "max": 3.5}},    
              63.0: {1: {"min":-1.5, "max": 1.5}, 2: {"min": -2.5, "max": 2.5}},
             125.0: {1: {"min":-1.5, "max": 1.5}, 2: {"min": -2.0, "max": 2.0}},
             250.0: {1: {"min":-1.4, "max": 1.4}, 2: {"min": -1.9, "max": 1.9}},
             500.0: {1: {"min":-1.4, "max": 1.4}, 2: {"min": -1.9, "max": 1.9}},
            }
        ref_spl += table_freq_weightings[nominal_frequency][frequency_weighting]
        dif = round(measured_spl - ref_spl, 2) + windshiled_correction + case_correction
        if(dif >= 0.0):
            dif += 0.21
        else:
            dif -= 0.21
        
        if tolerance_limits[nominal_frequency][1]["min"] <= dif <= tolerance_limits[nominal_frequency][1]["max"]:
            return 1
        elif tolerance_limits[nominal_frequency][2]["min"] <= dif <= tolerance_limits[nominal_frequency][2]["max"]:
            return 2
        else:
            return 3
        
    def linearity_tolerance_limits(self, deviation, uncertainty):
        """Use to define the class in Linearity measurement. Ref: ISO paragraph 5.5.5.
        Return 1, 2 or 3 (foul).
        """
        total = abs(deviation) + uncertainty
        if total <= 1.1:
            return 1
        elif total <= 1.4:
            return 2
        else:
            return 3

        
class Standard60651(object):
    def frequency_weighting_tolerance_limits(self, frequency_weighting,
                                             nominal_frequency, ref_spl,
                                             measured_spl, windshiled_correction,
                                             case_correction):
        # TODO different tables than 60672
        pass
    
# TODO accoustical signal Par. 11

class selectMethods(object):
    
    def __init__(self):
        self.root = Toplevel()
          
        self.frequency_weighting = BooleanVar()
        chk1 = Checkbutton(self.root, text="Frequency Weighting (61672-3 Electrical Tests, Par.12)",
                                              variable=self.frequency_weighting)
        chk1.pack()
        self.freq_time_weighting = BooleanVar()
        chk2 = Checkbutton(self.root, text="Frequency and Time Weighting (61672-3 Electrical Tests, Par.13)",
                           variable=self.freq_time_weighting)
        chk2.pack()
        self.linearity = BooleanVar()
        chk3 = Checkbutton(self.root, text="Linearity (61672-3 Electrical Tests Par.14, 15)",
                           variable=self.linearity)
        chk3.pack()       
        self.toneburst_response = BooleanVar()
        chk4 = Checkbutton(self.root, text="Toneburst response (61672-3 Electrical Tests Par.16)",
                           variable=self.toneburst_response)
        chk4.pack()
        self.peak_C_sound_level = BooleanVar()
        chk5 = Checkbutton(self.root, text="Peak C sound Level (61672-3 Electrical Tests Par.17)",
                           variable=self.peak_C_sound_level)
        chk5.pack()
        self.overload_indication = BooleanVar()
        chk6 = Checkbutton(self.root, text="Overload Indication (61672-3 Electrical Tests Par.18)",
                           variable=self.overload_indication)
        chk6.pack()
        b = Button(self.root,text='OK',command=self.get_selection)
        b.pack(side='bottom')

    def waitForInput(self):
        self.root.mainloop()
        
    def get_selection(self):
        self.root.withdraw()
        self.root.destroy()
        self.root.quit()

class takeInput(object):
    """Utility class to show popup and get user input string.
    """
    def __init__(self,requestMessage):
        self.root = Tk()
        self.root.after(2000, lambda: self.e.focus_force())
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
        
    def gettext(self, *args, **kwargs):
        self.string = self.e.get()
        self.root.withdraw()
        self.root.destroy()
        self.root.quit()

    def getString(self):
        return self.string

    def waitForInput(self):
        self.root.bind('<Return>', self.gettext)
        self.root.mainloop()

def getText(requestMessage):
    msgBox = takeInput(requestMessage)
    #loop until the user makes a decision and the window is destroyed
    msgBox.waitForInput()
    msg = msgBox.getString().strip()
    return msg

def wait(msg):
    """Wait until any key is pressed.
    """
    frequency = 2500  # Set Frequency To 2500 Hertz
    duration = 1000  # Set Duration To 1000 ms == 1 second
    winsound.Beep(frequency, duration)
    Tk().wm_withdraw() #to hide the main window
    tkMessageBox.showinfo("Calibration", msg)


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
        """General configuration is loaded from C:\acoustics-configuration\general.yaml 
        """
        #with open('C:/acoustics-configuration/slm-general.yaml', 'r') as stream:
        #    self.GENERAL_CONF = yaml.load(stream)     
        #    #assert self.GENERAL_CONF.get('ITERATIONS')
        #    #assert self.GENERAL_CONF.get('WAIT_BEFORE_SPL_MEASUREMENT')      
        m=self.mainapp              #a shortcut to the main app, especially the instruments
        f=self.frontpanel           #a shortcut to frontpanel values
        reserved_bus_access=self.GPIB_bus_lock     #a lock that reserves the access to the GPIB bus
               
        logging.info("Load conf from yaml file")
        root = Tk()
        calibration_conf = askopenfilename(parent=root)
        with open(calibration_conf, 'r') as stream:
            self.conf = yaml.load(stream)
        
        self.std61672 = Standard61672()
        
        logging.info("init all instruments")        
        self.keithley2001 = m.instr_1   # GBIP0::16
        self.agilent3350A = m.instr_2   # GBIP0::20
        self.el100 = m.instr_3          # GBIP0::3
        
        # DEBUG BURST            
        # self.agilent3350A.turn_on()
        # self.agilent3350A.start_burst(freq=4000, volt=0.1, delay=0.2, count=800)
        # self.agilent3350A.stop_burst()
                                
        if self.conf.get("standard") == "60651":
            self.run_60651()        
        elif self.conf.get("standard") == "61672-3":
            self.run_61672_3()
        else:
            logging.error("No valid standard selected")
            sys.exit(0)
    
    def run_60651(self):
        """Old standard
        """
        # TODO
        
        pass
    
    def run_61672_3(self):
        """New standard
        """
        options = selectMethods()
        options.waitForInput()                     
        if options.frequency_weighting:
            self.frequency_weightings()
        if options.linearity:
            self.linearity()
        if options.freq_time_weighting:
            self.freq_time_weighting()
        if options.overload_indication:
            self.overload_indication_measurement()
        if options.peak_C_sound_level:
            self.peak_C_sound_level()
        if options.toneburst_response:
            self.toneburst_response()
        print("END OF MEASUREMENTS")
        sys.exit(0)
        
    def frequency_weightings(self):
        """Initial el100 value is not fixed. It is calculated by SLM manual values.
        Max linearity range (e.g. 140) - 45 (fixed by standard 61672)
        We run the frequency weighting 3 times (A, C, Z).
        We do NOT change anything in our code/process, only SLM device settings
        change.
        Reference SPL comes from the manufacturer.
        """
        linear_operating_range = self.conf.get("linear_operating_range")
        self.agilent3350A.set_frequency(1000.0, volt=0.5)
        
        spl_aim = linear_operating_range.get("max") - 45
        
        self.el100_ref_value = float(getText(
            "What is the attenuator value when SLM value is %g?" % spl_aim))
        
        frequencies = self.conf.get('frequencies')
        case_corrections = self.conf.get('case_corrections')
        windshield_corrections = self.conf.get('windshield_corrections')
        level_ranges = self.conf.get('level_ranges')
        upper_ref_level_range = level_ranges[0][0]
        lower_ref_level_range = level_ranges[0][1]
        for weighting in ["A", "C", "Z"]:
            wait("Please set your Sound Level Meter REF level range (%g, %g) and %s weighting and press any key to continue." % (
                upper_ref_level_range, lower_ref_level_range, weighting))
            results = []
            for freq in frequencies:
                self.agilent3350A.set_frequency(freq, volt=4.0)
                slm_reading = float(getText("Frequency = %g. What is the SLM reading (dB)?" % freq))    
                overall_response = slm_reading + case_corrections[freq] + windshield_corrections[freq]
                slm_class = self.std61672.frequency_weighting_tolerance_limits(
                    weighting, freq, 95.0, slm_reading, windshield_corrections[freq], case_corrections[freq])    
                
                row = [freq, self.el100_ref_value, slm_reading, windshield_corrections[freq], case_corrections[freq],
                       overall_response, slm_class]
                results.append(row)
        
            print("Frequency Weighting %s Results" % weighting)
            print("Frequency    Attn    Slm reading    Windshield corr    Case corr    Overall response    Class")
            print("   (Hz)      (dB)       (dB)            (dB)              (dB)            (dB)")
            for row in results:
                print("%.1f      %.2f        %.2f          %.2f              %.2f            %.2f            %d" % (
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6]))        
    
    def linearity(self):
        """1. The problem is that we need to set an ACPP value to get
        attenuator ~50+-10.
        If we get initial attenuator value very low or high, there will be
        a problem with other measurements.
        2. Tune attenuator until SPL = 99 (94 + 5) ...
        Uncertainty is fixed 0.2
        
        COLUMNS
        Nominal SPL (dB)    Attn Setting (dB)    Diff ref  RefSPL    Nom Diff    Deviation    Uncertainty (dB) Class
        """
        linear_operating_range = self.conf.get('linear_operating_range')
        range_lower = linear_operating_range.get('min')
        ref_point_linearity_check = 94 # FIXED value
        range_upper = linear_operating_range.get('max')      
        
        range_upper = range(ref_point_linearity_check, int(range_upper) - 4, 5) + \
                        range(int(range_upper) -4, int(range_upper) + 1)
        range_lower = range(ref_point_linearity_check, int(range_lower) + 5, -5) + \
                        range(int(range_lower) + 5, int(range_lower) - 1)
        
        logging.info("ranges")
        logging.info(range_lower)
        logging.info(range_upper)

        wait("Please configure SLM to A weighting at reference level range [%g, %g]." % (
             range_lower, range_upper))
        
        self.agilent3350A.set_frequency(self.conf.get('generator_frequency'),
                                        volt=self.conf.get('generator_voltage'))  # ACPP (peak to peak). TODO what is the correct volt value??
        
        # TODO save keithley value after we set agilent frequency for ALL linearity measurements       
        ref_attenuation = float(getText("What is the attenuator value when SLM reads %g (dB)?" % ref_point_linearity_check))        
        
        results = []
        for slm in range_upper:
            atten = float(getText("What is the attenuator value when SLM reads %g (dB)?" % slm))
            # SKIP line when atten = 0 (cannot reach the SLM value)
            if atten == 0.0:
                continue
            dif_ref_refspl = slm -  ref_point_linearity_check # TODO ???
            nom_dif = slm -  ref_point_linearity_check
            deviation = dif_ref_refspl - nom_dif
            voltage = self.keithley2001.query_voltage()
            uncertainty = 0.2
            linearity_class = self.std61672.linearity_tolerance_limits(deviation, uncertainty)
            results.append([atten, dif_ref_refspl, nom_dif, deviation, uncertainty, voltage, linearity_class])
            
        for slm in range_lower:
            atten = float(getText("What is the attenuator value when SLM reads %g (dB)?" % slm))
            # SKIP line when atten = 0 (cannot reach the SLM value)
            if atten == 0.0:
                continue
            dif_ref_refspl = slm -  ref_point_linearity_check # TODO ???
            nom_dif = slm -  ref_point_linearity_check
            deviation = dif_ref_refspl - nom_dif
            voltage = self.keithley2001.query_voltage()
            uncertainty = 0.2
            linearity_class = self.std61672.linearity_tolerance_limits(deviation, uncertainty)
            results.append([atten, dif_ref_refspl, nom_dif, deviation, uncertainty, voltage, linearity_class])
                       
        print("Linearity Test")
        print("Nominal SPL    Attn Setting    Diff re RefSpl    Nom Diff    Dvm Rdg    Voltage Class")
        print("    (dB)            (dB)            (dB)            (dB)       (dB)      (V)         ")
        for row in results:
            print("    %.1f        %.2f        %.2f        %.2f        %.2f    %.2f        %d" % (
                row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
        
        """if level ranges has multiple values beyond REF, perform extra test.
        Document reference: New IEC Standards and Periodic Testing of Sound Level Meters.
        Section 6.9, standard 61672-3 clause 15.2 15.3 15.4
        Note that agilent is already set to 8000 Hz and volt TODO ACPP
        """
        self.agilent3350A.set_frequency(1000.0, volt=self.conf.get('generator_voltage'))
        level_ranges = self.conf.get('level_ranges')
        if len(level_ranges) > 1:
            ref_atten = None
            ref_slm = None
            results = []
            for lrange in level_ranges[1:]:
                wait("Please configure SLM to A weighting at reference level range [%g, %g]." % (lrange[0], lrange[1]))
                wait("Please set attenuator value to %f" % ref_attenuation)
                slm = float(getText("What is the SLM value?"))
                if not ref_slm:
                    ref_slm = slm                    
                deviation = ref_slm - slm
                uncertainty = 0.2
                linearity_class = self.std61672.linearity_tolerance_limits(deviation, uncertainty)
                results.append(["%.2f - %.2f" % (lrange[0], lrange[1]),
                                ref_slm,
                                slm,
                                deviation,
                                uncertainty,
                                linearity_class])
                    
            def _print_slm_range_results(results):
                print("SLM range setting    Expected value    SLM Reading value    Deviation    Uncertainty    Class")
                print("      (dB)                (dB)                (dB)            (dB)            (dB)        ")
                for row in results:
                    print("    %s        %.2f           %.2f            %.2f        %.2f          %d" % (
                        row[0], row[1], row[2], row[3], row[4], row[5]))
        
            _print_slm_range_results(results)
        
            """Document reference: New IEC Standards and Periodic Testing of Sound Level Meters.
            Section 6.9, standard 61672-3 clause 15.4
            """
            results = []
            self.agilent3350A.set_frequency(1000.0, volt=self.conf.get('generator_voltage'))
            ref_atten = float(getText("What is the attenuator value when SLM reads %g (dB) (upper limit - 5)?" % lrange[1] - 5))
            for lrange in level_ranges[1:]:
                wait("Please configure SLM to A weighting at reference level range [%g, %g]." % (lrange[0], lrange[1]))
                slm = float(getText("What is the SLM value?"))
                if not ref_slm:
                    ref_slm = slm                    
                deviation = ref_slm - slm
                uncertainty = 0.2
                linearity_class = self.std61672.linearity_tolerance_limits(deviation, uncertainty)
                results.append(["%.2f - %.2f" % (lrange[0], lrange[1]),
                                ref_slm,
                                slm,
                                deviation,
                                uncertainty,
                                linearity_class])
        
            _print_slm_range_results(results)
    
    def freq_time_weighting(self):
        """ISO61672-3 Electrical Tests Par. 13
        Ref: row 131 of excel 2250Asteroskopeio
        """
        ref_point_linearity_check = 94 # FIXED value
        self.agilent3350A.set_frequency(1000.0, volt=2.0)
        ref_attenuation = float(getText("What is the attenuator value when SLM reads %g (dB)?" % ref_point_linearity_check))
                
        # FAST time weighting
        results = []
        for weighting in ["A", "C", "Z"]:
            slm = float(getText("Please set your SLM to %s weighting and write your SLM value." % weighting))
            deviation = ref_point_linearity_check - slm
            uncertainty = 0.2
            time_weighting_class = self.std61672.linearity_tolerance_limits(deviation, uncertainty)
            results.append([weighting,
                            ref_point_linearity_check,
                            slm,
                            deviation,
                            uncertainty,
                            time_weighting_class])
        
        print("Time weighting F    Expected Value    SLM reading value    Deviation    Uncertainty    Class")
        print("                         (dB)               (dB)              (dB)          (dB)")
        for row in results:
            print("%s        %.2f        %.2f        %.2f        %.2f        %d" % (row[0], row[1], row[2], row[3], row[4], row[5]))
        
        # SLOW time weighting
        for weighting in ["A", "C", "Z"]:
            slm = float(getText("Please set your SLM to %s weighting and write your SLM value." % weighting))
            deviation = ref_point_linearity_check - slm
            uncertainty = 0.2
            time_weighting_class = self.std61672.linearity_tolerance_limits(deviation, uncertainty)
            results.append([weighting,
                            ref_point_linearity_check,
                            slm,
                            deviation,
                            uncertainty,
                            time_weighting_class])
        print("Time weighting S    Expected Value    SLM reading value    Deviation    Uncertainty    Class")
        print("                         (dB)               (dB)              (dB)          (dB)")
        for row in results:
            print("%s        %.2f        %.2f        %.2f        %.2f        %d" % (row[0], row[1], row[2], row[3], row[4], row[5]))
        
    def overload_indication_measurement(self):
        """ISO61672-3 Paragraph 18
        least-sensitive level range with the sound level meter set to A-weighted time-average sound level.
        
        Attenuator adjusted to an SLM Reading of X dB for the continuous signal
        # target_db = ref upper range - 1
        # level overload indication (positive half cycle)
        # program Agilent to make a custom positive waveform
        # TODO level overload indication (negative half cycle)
        # program Agilent to make a custom negative waveform.
        # excel line 359.
        
        # Attenuator reading = 9.06 dB
        # SLM reading = 123.28 dB
        # Nominal reading = 123 dB
        
        # TODO signal increased until SLM overload ??
        # SLM Reading = 125.74 dB
        # Signal reduced by 1 dB    SLM Reading = 124.74 dB
        # Signal reduced by 3 dB    SLM Reading = 121.74 dB
        #     Nominal SLM Reading = 121.74 dB
        # 
        # attenuator increase step = 0.5 dB WARNING when we find overload, we should
        # tune to the previous value
        # then use step = 0.1 dB until the first indication of overload.
        """
        level_ranges = self.conf.get('level_ranges')
        upper_ref_level_range = level_ranges[0][0]
        lower_ref_level_range = level_ranges[0][1]
        weighting = "A"
        wait("Please set your Sound Level Meter REF level range (%g, %g) and %s weighting and press any key to continue." % (
                upper_ref_level_range, lower_ref_level_range, weighting))

        slm_initial = upper_ref_level_range - 1
        self.agilent3350A.set_frequency(freq=4000, volt=0.5)
        atten_positive = float(getText("What is the attenuator value when SLM reads %g (dB)?" % slm_initial))
        self.agilent3350A.turn_off()
        
        # TODO problem
        # Initially we have atten = 12.3 and SLM value = 119
        # When we enable positive half cycle, we get overload ASAP
        # So, we reduce atten to 11.8 and then start increasing by 0.1
        # Finally we get overload atten value less than 12.3???
        
        def _measure():    
            atten = atten_positive
            step = 0.5
            while(True):
                answer = getText("Do we have an overload in the Sound Level Meter? (y / n)").lower()
                if answer == "y":
                    if step == 0.5:
                        atten -= step
                        step = 0.1
                        logging.info("Switching to step 0.1")
                    elif step == 0.1:
                        atten_overload = atten
                        slm_overload = float(getText("What is the current SLM value?"))
                        slm_diff = slm_overload - slm_initial
                        uncertainty = 0.2
                        myclass = 1 if -1.8 <= slm_diff <= 1.8 else 2
                        return (slm_initial, atten_positive, slm_overload, atten_overload, slm_diff, uncertainty, myclass)                         
                atten += step
                self.el100.set("%05.2f" % atten)

        self.agilent3350A.positive_half_cycle(freq=4000, volt=0.5)
        all_results = []
        row = _measure()
        all_results.append(row)
        print("initial SLM | atten | overload SLM | atten | diff SLM | uncertainty | class")
        print("   %.2f     %.2f      %.2f      %.2f       %.2f       %.2f       %d" % (
              row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
        self.agilent3350A.turn_off()
        
        self.agilent3350A.negative_half_cycle(freq=4000, volt=0.5)
        row = _measure()
        all_results.append(row)
        self.agilent3350A.turn_off()
        
        print("initial SLM | atten | overload SLM | atten | diff SLM | uncertainty | class")
        for row in all_results:
            print("   %.2f     %.2f      %.2f      %.2f       %.2f       %.2f     %d" % (
                  row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
  
    
    def peak_C_sound_level(self):
        """ISO61672-3 Paragraph 17
        Only for C-weighted sound level
        least-sensitive sound range
        8khz SIN start and stop at zero crossings.
        positive and negative half cycles of a 500 Hz sinusoid.
        TODO cannot understand 17.3
        """
        #level_ranges = self.conf.get('level_ranges')
        #upper_ref_level_range = level_ranges[0][0]
        #lower_ref_level_range = level_ranges[0][1]
        upper_range = 120.0 # ? TODO
        lower_range = 40.0  # ? TODO
        weighting = "C"
        wait("Please set your Sound Level Meter to %s weighting and the least sensitive level range (%g, %g)." % (
             weighting, upper_range, lower_range))
        
        target_slm = upper_range - 8.0      
        
        print("Peak C.    LCpeak-LC    Expected    SLM SLM  SLM    SLM    Deviation    Uncertainty    Class")
        print("Response                  (dB)       m1  m2   m3    avg       (dB)          (dB)")
        
        def _measure_print(step, label, offset):
            expected = target_slm + offset
            row = [label, offset,  expected]
            for _ in range(3):
                if step == 1:
                    self.agilent3350A.set_frequency(freq=8000, volt=0.1)
                elif step == 2:
                    self.agilent3350A.start_burst(freq=8000, volt=0.1, delay=0, count=1)
                elif step == 3:
                    self.agilent3350A.positive_half_cycle(freq=500, volt=0.1)
                elif step == 4:
                    self.agilent3350A.negative_half_cycle(freq=500, volt=0.1)
                time.sleep(3)
                slm_val = float(getText("What is the SLM value (dB)?"))
                if step == 2:
                    self.agilent3350A.stop_burst()
                self.agilent3350A.turn_off()
                row.append(slm_val)
                wait("Please reset your SLM.")
            slm_avg = (row[3] + row[4] + row[5]) / 3.0
            row.append(slm_avg)
            deviation = row[3] - row[2] # (SLM m1 - expected) ??? This seems wrong TODO check.
            row.append(deviation)
            row.append(0.2) # uncertainty
            
            if step == 1:
                myclass = 1 if -1.4 < deviation < 1.4 else 2
            elif step == 2:
                myclass = 0
            elif step == 3 or step == 4:
                myclass = 1 if -2.4 < deviation < 2.4 else 2
                    
            row.append(myclass)
            return row
        
        def _print_row(row):
            print("%s    %g    %g    %g    %g    %g    %g    %g    %g    %d" % (
                  row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7],
                  row[8], row[9]))
        
        all_results = []
        # Steady 8Khz
        row = _measure_print(step=1, label="Steady 8Khz", offset=0.0)
        all_results.append(row)
        _print_row(row)
        
        # Burst with 1 cycle, 8Khz
        row = _measure_print(step=2, label="1 cycle 8Khz", offset=3.4)       
        all_results.append(row)
        _print_row(row)
        
        # Positive half cycle 500Hz
        row = _measure_print(step=3, label="Positive half cycle", offset=2.4)
        all_results.append(row)
        _print_row(row)
                
        # Negative half cycle 500Hz
        row = _measure_print(step=4, label="Negative half cycle", offset=2.4)
        all_results.append(row)
        _print_row(row)
        
    def toneburst_response(self):
        """ISO61672-3 Electrical Tests Par. 16      
        # continuous setting = LAF
        # Fast setting = LAF MAX
        # Slow setting = LAS MAX
        # LA eq (equivalent)
        
        Process:
        1. Start agilent in normal mode and set volt to initial `generator_voltage` from conf.
        2. Increase in small steps and check SLM value. The aim is to reach value = upper_level_range value - 3
        (e.g. 140 - 3 = 137). Save the voltage and continue.
        3. Enable burst mode (EXCEL 2250Asteroskopio3 ROW 310)        
        """
        self.el100.set('00.00')
        level_ranges = self.conf.get('level_ranges')
        upper_ref_level_range = level_ranges[0][0]
        lower_ref_level_range = level_ranges[0][1]
        weighting = "A"
        wait("Please set your Sound Level Meter REF level range (%g, %g) and %s weighting and press any key to continue." % (
             upper_ref_level_range, lower_ref_level_range, weighting))
       
        slm_aim = upper_ref_level_range - 3.0
        volt = 0.1
        while True:
            self.agilent3350A.set_frequency(freq=4000, volt=volt)
            new_volt = float(getText("The aim is to reach SPM %g (dB). Voltage = %g. Please set a new voltage. Set 0 to save and continue." % (
                                     slm_aim, volt)))
            if new_volt == 0:
                volt_identified = volt
                self.agilent3350A.turn_off()
                break       
            else:
                volt = new_volt   
    
        runs = [dict(setting="Fast (LAF MAX)",
                     opts=[dict(delay=0.2, cycles=800, offset=-1, min_tolerance=-0.8, max_tolerance=0.8),
                           dict(delay=0.002, cycles=8, offset=-18, min_tolerance=-1.8, max_tolerance=1.3),
                           dict(delay=0.00025, cycles=1, offset=-27, min_tolerance=-3.3, max_tolerance=1.3)]),
                dict(setting="Slow (LAF MAX)",
                     opts=[dict(delay=0.2, cycles=800, offset=-1, min_tolerance=-0.8, max_tolerance=0.8),
                           dict(delay=0.002, cycles=8, offset=-18, min_tolerance=-1.8, max_tolerance=1.3)]),
                dict(setting="LA eq (equivalent)",
                     opts=[dict(delay=0.2, cycles=800, offset=-1, min_tolerance=-0.8, max_tolerance=0.8),
                           dict(delay=0.002, cycles=8, offset=-18, min_tolerance=-1.8, max_tolerance=1.3),
                           dict(delay=0.00025, cycles=1, offset=-27, min_tolerance=-3.3, max_tolerance=1.3)])]
        
        for run in runs:
            results = []
            for opt in run['opts']:
                slm_results = []
                slm_expected = slm_aim + opt['offset']
                for _ in range(3):
                    wait("Please use SLM setting %s and reset instrument." % run['setting'])    
                    self.agilent3350A.turn_on()
                    self.agilent3350A.start_burst(freq=4000, volt=volt_identified,
                                                  delay=opt['delay'], count=opt['cycles'])
                    self.agilent3350A.stop_burst()
                    self.agilent3350A.turn_off()
                    slm_reading = float(getText("Voltage = %g. What is the SLM reading (dB)? Expected value is %g." % (
                                                volt, slm_expected)))
                    slm_results.append(slm_reading)
                slm_avg = sum(slm_results) / len(slm_results)
                slm_deviation = slm_avg - slm_expected
                uncertainty = 0.2
                if opt['min_tolerance'] <= slm_deviation <= opt['max_tolerance']:
                    myclass = 1
                else:
                    myclass = 2           
                result = [opt['delay'], opt['cycles'], opt['offset'], slm_expected,
                          slm_results[0], slm_results[1], slm_results[2], slm_avg,
                          slm_deviation, uncertainty, myclass]
                results.append(result)
            
            print(run['setting']) 
            print("Burst   Burst Cycles    LAFmax-LA   Expected    SLM    SLM    SLM   SLM   Deviation    Unc    Class")
            print("Delay                  (IEC 61672-1              m1     m2     m3   avg")   
            print("(ms)        (N)         Table 3)      (dB)      (dB)   (dB)   (dB)  (dB)   (dB)       (dB)")
            for r in results:
                print("%g       %g        %g        %g        %g    %g    %g    %g    %g        %g    %g" % (
                      r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]))