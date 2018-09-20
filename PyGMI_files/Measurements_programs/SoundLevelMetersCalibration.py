import logging 
import threading
import sys
import time
from Tkinter import Tk
from tkFileDialog import askopenfilename
import yaml

from ..eim.tkutils import (wait, selectMethods616723, selectMethods60651,
                           getText)


def linearity_tolerance_limits(deviation, uncertainty):
    """Use to define the class in Linearity measurement.
    Ref: ISO paragraph 5.5.5.
    Return 1, 2 or 666 (foul).
    """
    total = abs(deviation) + uncertainty
    if total <= 1.1:
        return 1
    elif total <= 1.4:
        return 2
    else:
        return 666

######create a separate thread to run the measurements without freezing the front panel######
class Script(threading.Thread):
                
    def __init__(self, mainapp, frontpanel, data_queue, stop_flag,
                 GPIB_bus_lock, **kwargs):
        threading.Thread.__init__(self,**kwargs)
        self.mainapp=mainapp
        self.frontpanel=frontpanel
        self.data_queue=data_queue
        self.stop_flag=stop_flag
        self.GPIB_bus_lock=GPIB_bus_lock
        
    def run(self):
        """General configuration is loaded from
        C:\acoustics-configuration\general.yaml 
        """
        #with open('C:/acoustics-configuration/slm-general.yaml', 'r') as stream:
        #    self.GENERAL_CONF = yaml.load(stream)     
        #    assert self.GENERAL_CONF.get('ITERATIONS')
        #    assert self.GENERAL_CONF.get('WAIT_BEFORE_SPL_MEASUREMENT')      
        # a shortcut to the main app, especially the instruments
        m = self.mainapp          
        
        logging.info("init all instruments")        
        self.keithley2001 = m.instr_1 # GBIP0::16
        self.wgenerator = m.instr_2   # GBIP0::20 Agilent GBIP::10 Keysight
        self.el100 = m.instr_3        # GBIP0::3
                                                
        logging.info("Load conf from yaml file")
        root = Tk()
        calibration_conf = askopenfilename(parent=root)
        with open(calibration_conf, 'r') as stream:
            self.conf = yaml.load(stream)
                                        
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
        # TODO add conf variable PIR_INDICATOR_RANGE: 125
        
        options = selectMethods60651()
        options.waitForInput()
        
        if options.acoustic_test.get():
            self.acoustic_test()
        if options.self_generated_noise_test.get():
            self.self_generated_noise_test()
        if options.frequency_weighting.get():
            self.frequency_weightings()
            # TODO question: 60651 results have a PASS/FAIL column.
            # This is the only difference between 60651 and 61672-3.
        if options.linearity.get():            
            self.linearity()
            # TODO question: 60651 results have a PASS/FAIL column.
            # This is the only difference between 60651 and 61672-3.
        if options.time_weighting.get():    
            self.time_weighting60651()
            # 61672-3 has target SLM = max - 45 dB.
            # 60651 has target SLM = PIR_UPPER_LIMIT - 4
            # What is the PASS/FAIL limit?
            pass
        if options.rms_accuracy_and_overload.get():
            self.rms_accuracy_and_overload60651()
            pass
        if options.peak_response.get():
            self.peak_response60651()
            pass       
        if options.time_averaging.get():
            self.time_averaging60651()
            pass
        if options.pulse_range_sound_exposure_level_and_overload.get():
            self.pulse_range_sound_exposure_level_and_overload60651()
            pass            
            
        print("END OF MEASUREMENTS")
        sys.exit(0)
    
    def run_61672_3(self):
        """New standard
        """
        options = selectMethods616723()
        options.waitForInput()
        if options.acoustic_test.get():
            self.acoustic_test()
        if options.self_generated_noise_test.get():
            self.self_generated_noise_test()                
        if options.frequency_weighting.get():
            self.frequency_weightings()
        if options.linearity.get():
            self.linearity()
        if options.freq_time_weighting.get():
            self.freq_time_weighting()
        if options.overload_indication.get():
            self.overload_indication_measurement()
        if options.peak_C_sound_level.get():
            self.peak_C_sound_level()
        if options.toneburst_response.get():
            self.toneburst_response()
        
        print("END OF MEASUREMENTS")
        sys.exit(0)
    
    def reset_instruments(self, el100=0.0):
        """Called before and after every measurement
        """
        self.wgenerator.turn_off()
        self.el100.set(el100)
        
    def acoustic_test(self):
        """125 Hz, 1, 4, 8 Khz
        Excel line 24. TODO???
        """        
        wtitle = "Acoustic Test"
    
        calibrator_conf = self.conf.get('calibrator')
        # manufacturer: "B&K"
        # type: "4231"
        # serial_number: "2218152"
        # spl: 94.0     # from certificate
        # free_field_correction: -0.15        # from certificate
        # windscreen_correction: -0.2
        # pressure_correction: 0.0
        corrected_spl = calibrator_conf.get('spl') + \
                        calibrator_conf.get('free_field_correction') + \
                        calibrator_conf.get('windscreen_correction') + \
                        calibrator_conf.get('pressure_correction')
        
        lrange = self.conf.get('linear_operating_range')
        lrange_min = lrange.get("min")
        lrange_max = lrange.get("max")
        wait("Please connect customer SLM and EIM reference calibrator.", title=wtitle)
        wait("Please configure the SLM to use A weighting and range %g, %g dB." % (lrange_min, lrange_max))
                
        res = []
        for _ in range(3):
            slm_val = float(getText("What is the SLM reading (dB)?",
                                    title=wtitle))
            res.append(slm_val)
            time.sleep(3)
        avg = sum(res) / 3.0
        diff = abs(avg - corrected_spl)
        print("SLM Reading %g %g %g dB, average: %g dB, diff: %g dB" % (
              res[0], res[1], res[2], avg, diff))
        if diff <= calibrator_conf.get('spl_tolerance'):
            print("PASS")
        else:
            print("FAIL")
            wait("Please adjust SLM and repeat the test.")
        
        # TODO to be continued...
        
        
    def frequency_weightings(self):
        """Initial el100 value is not fixed. It is calculated by SLM manual values.
        Max linearity range (e.g. 140) - 45 (fixed by standard 61672)
        We run the frequency weighting 3 times (A, C, Z).
        We do NOT change anything in our code/process, only SLM device settings
        change.
        Reference SPL comes from the manufacturer.
        
        Use the same method for ISO 60651 and 61672-3.
        """
        self.reset_instruments(el100=99.00)
        linear_operating_range = self.conf.get("linear_operating_range")
        self.wgenerator.set_frequency(1000.0, volt=0.5)
        self.wgenerator.turn_on()
        
        spl_aim = linear_operating_range.get("max") - 45
        
        wait("Please set your Sound Level Meter to A weighting and tune the attenuator until SLM value is %g." % spl_aim)
                        
        self.el100_ref_value = self.el100.get() 
        
        print("Waveform Generator %g Hz, %g V, attenuator %g dB, SLM %g dB" % (
              1000.0, 0.5, self.el100_ref_value, spl_aim))
        
        """ISO61672-1 IEC:2002, Table 2, Page 33.
        Frequency_weighting = 'A', 'C' or 'Z'
        NOTE that there is a standard uncertainty budget = 0.21
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
                self.wgenerator.set_frequency(freq, volt=0.5)
                slm_reading = float(getText("Frequency = %g. What is the SLM reading (dB)?" % freq))    
                overall_response = slm_reading + case_corrections[freq] + windshield_corrections[freq]
    
                expected = spl_aim + table_freq_weightings[freq][weighting]
                deviation = round(slm_reading - expected + windshield_corrections[freq] + case_corrections[freq], 2)
                if(deviation >= 0.0):
                    deviation += 0.21
                else:
                    deviation -= 0.21
                if tolerance_limits[freq][1]["min"] <= deviation <= tolerance_limits[freq][1]["max"]:
                    slm_class = 1
                elif tolerance_limits[freq][2]["min"] <= deviation <= tolerance_limits[freq][2]["max"]:
                    slm_class = 2
                else:
                    slm_class = 666
                
                row = [freq, self.el100_ref_value, slm_reading, windshield_corrections[freq],
                       case_corrections[freq], overall_response, expected, deviation, slm_class]
                print(row)
                results.append(row)
                
            print("Frequency Weighting %s Results" % weighting)
            print("Frequency    Attn    Slm reading    Windshield corr    Case corr    Overall response  Expected Deviation    Class")
            print("   (Hz)      (dB)       (dB)             (dB)            (dB)            (dB)           (dB)     (dB)")
            for row in results:
                print("%6.1f      %.2f       %.2f          %.2f            %.2f            %.2f        %.2f        %.2f       %d" % (
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))        
        self.reset_instruments()
    
    def linearity(self):
        """1. The problem is that we need to set an ACPP value to get
        attenuator ~50+-10.
        If we get initial attenuator value very low or high, there will be
        a problem with other measurements.
        2. Tune attenuator until SPL = 99 (94 + 5) ...
        Uncertainty is fixed 0.2
        
        Use the same method in 60651 and 61672-3. The only difference is the PASS/FAIL column.
        
        COLUMNS
        Nominal SPL (dB)    Attn Setting (dB)    Diff ref  RefSPL    Nom Diff    Deviation    Uncertainty (dB) Class
        """
        wtitle = "Linearity (61672-3 Electrical Tests Par.14, 15)"
        self.reset_instruments()
        linear_operating_range = self.conf.get('linear_operating_range')
        ref_range_lower = linear_operating_range.get('min')
        ref_point_linearity_check = 94 # FIXED value
        ref_range_upper = linear_operating_range.get('max')      
        target_slm = ref_range_upper
        
        range_upper = range(ref_point_linearity_check, int(ref_range_upper) - 4, 5) + \
                        range(int(ref_range_upper) -4, int(ref_range_upper) + 1)
        range_lower = range(ref_point_linearity_check, int(ref_range_lower) + 5, -5) + \
                        range(int(ref_range_lower) + 5, int(ref_range_lower) - 1)
        
        logging.info("ranges")
        logging.info(range_lower)
        logging.info(range_upper)

        wait("Please configure SLM to LAF weighting at reference level range [%g, %g]." % (
             ref_range_lower, ref_range_upper))
                
        (target_volt, target_atten) = self._tune_wgenerator(8000, target_slm, wtitle)       
        self.wgenerator.turn_on()
        results = []
        for slm in range_upper:
            wait("Please tune the attenuator until SLM reads %g dB." % slm)
            atten = self.el100.get()
            # SKIP line when atten = 0 (cannot reach the SLM value)
            if atten == 0.0:
                continue
            dif_ref_refspl = slm -  ref_point_linearity_check # TODO ???
            nom_dif = slm -  ref_point_linearity_check
            deviation = dif_ref_refspl - nom_dif
            voltage = self.keithley2001.query_voltage()
            uncertainty = 0.2
            linearity_class = linearity_tolerance_limits(deviation, uncertainty)
            results.append([atten, dif_ref_refspl, nom_dif, deviation, uncertainty, voltage, linearity_class])
            
            # tune atten for next iteration
            if atten > 5.0:
                atten -= 5.0
                self.el100.set(atten)
            elif atten > 1.0:
                atten -= 1.0
                self.el100.set(atten)
        for slm in range_lower:
            wait("Please tune the attenuator until SLM reads %g dB." % slm)
            atten = self.el100.get()
            # SKIP line when atten = 0 (cannot reach the SLM value)
            if atten == 0.0:
                continue
            dif_ref_refspl = slm -  ref_point_linearity_check # TODO ???
            nom_dif = slm -  ref_point_linearity_check
            deviation = dif_ref_refspl - nom_dif
            voltage = self.keithley2001.query_voltage()
            uncertainty = 0.2
            linearity_class = linearity_tolerance_limits(deviation, uncertainty)
            results.append([atten, dif_ref_refspl, nom_dif, deviation, uncertainty, voltage, linearity_class])
            # tune atten for next iteration
            if atten < 95.0:
                atten += 5.0
                self.el100.set(atten)
            elif atten < 99.0:
                atten += 1.0
                self.el100.set(atten)
                       
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
        (target_volt, target_atten) = self._tune_wgenerator(1000, target_slm, wtitle)
        self.wgenerator.turn_on()       
        level_ranges = self.conf.get('level_ranges')
        if len(level_ranges) > 1:
            ref_atten = None
            ref_slm = None
            results = []
            for lrange in level_ranges[1:]:
                wait("Please configure SLM to A weighting at reference level range [%g, %g]." % (lrange[0], lrange[1]))
                wait("Please set attenuator value to %f" % target_atten)
                slm = float(getText("What is the SLM value?"))
                if not ref_slm:
                    ref_slm = slm                    
                deviation = ref_slm - slm
                uncertainty = 0.2
                linearity_class = linearity_tolerance_limits(deviation, uncertainty)
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
            self.wgenerator.set_frequency(1000.0, volt=target_volt)
            self.wgenerator.turn_on()
            wait("Please configure the attenuator so that SLM reads %g dB (upper limit -5)" % (lrange[1] - 5))
            ref_atten = self.el100.get()
            for lrange in level_ranges[1:]:
                wait("Please configure SLM to A weighting at reference level range [%g, %g]." % (lrange[0], lrange[1]))
                slm = float(getText("What is the SLM value?"))
                if not ref_slm:
                    ref_slm = slm                    
                deviation = ref_slm - slm
                uncertainty = 0.2
                linearity_class = linearity_tolerance_limits(deviation, uncertainty)
                results.append(["%.2f - %.2f" % (lrange[0], lrange[1]),
                                ref_slm,
                                slm,
                                deviation,
                                uncertainty,
                                linearity_class])
        
            _print_slm_range_results(results)
            print("Attenuator value: %g" % ref_atten)
        
        self.reset_instruments()
    
    def freq_time_weighting(self):
        """ISO61672-3 Electrical Tests Par. 13
        Ref: row 131 of excel 2250Asteroskopeio
        """
        self.reset_instruments(el100=99.00)
        ref_point_linearity_check = 94 # FIXED value
        self.wgenerator.set_frequency(1000.0, volt=2.0)
        wait("Please configure the attenuator value so that SLM reads %g dB." % ref_point_linearity_check)
        ref_attenuation = self.el100.get()
                        
        # FAST time weighting
        results = []
        for weighting in ["A", "C", "Z"]:
            slm = float(getText("Please set your SLM to %sF weighting and write your SLM value." % weighting))
            deviation = ref_point_linearity_check - slm
            uncertainty = 0.2
            time_weighting_class = linearity_tolerance_limits(deviation, uncertainty)
            results.append([weighting,
                            ref_point_linearity_check,
                            slm,
                            deviation,
                            uncertainty,
                            time_weighting_class])
        
        print("Time weighting F    Expected Value    SLM reading value    Deviation    Uncertainty    Class")
        print("                         (dB)               (dB)              (dB)          (dB)")
        for row in results:
            print("%sF        %.2f        %.2f        %.2f        %.2f        %d" % (row[0], row[1], row[2], row[3], row[4], row[5]))
        
        
        results = []
        # SLOW time weighting
        for weighting in ["A", "C", "Z"]:
            slm = float(getText("Please set your SLM to %sS weighting and write your SLM value." % weighting))
            deviation = ref_point_linearity_check - slm
            uncertainty = 0.2
            time_weighting_class = linearity_tolerance_limits(deviation, uncertainty)
            results.append([weighting,
                            ref_point_linearity_check,
                            slm,
                            deviation,
                            uncertainty,
                            time_weighting_class])
        print("Time weighting S    Expected Value    SLM reading value    Deviation    Uncertainty    Class")
        print("                         (dB)               (dB)              (dB)          (dB)")
        for row in results:
            print("%sS        %.2f        %.2f        %.2f        %.2f        %d" % (row[0], row[1], row[2], row[3], row[4], row[5]))
        print("Attenuator value: %g" % ref_attenuation)
        self.reset_instruments()

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
        self.reset_instruments()
        
        wtitle = "Overload Indication (61672-3 Electrical Tests Par.18)" 
        lrange = self.conf.get('least_sensitive_level_range')
        upper_range = lrange[0]
        lower_range = lrange[1]
        weighting = "A"
        wait("Please set your Sound Level Meter REF level range (%g, %g) and %s weighting and press any key to continue." % (
             upper_range, lower_range, weighting), title=wtitle)

        self.el100.set("20.00") # Must start with a high value and the decrease it
        slm_initial = upper_range - 1
        (target_volt, atten_positive) = self._tune_wgenerator(4000, slm_initial, wtitle)
                
        def _measure():    
            atten = atten_positive
            step = 0.5
            switch_step = True
            while(True):
                answer = getText("Do we have an overload in the Sound Level Meter? (y / n)").lower()
                if answer == "y":
                    if step == 0.5:
                        step = 0.1
                        logging.info("Switching to step 0.1")
                    elif step == 0.1:
                        # When we switch from 0.5 to 0.1, we go back 0.5. This happens only once.
                        if switch_step:
                            atten += 1.0
                            switch_step = False
                        
                        atten_overload = atten
                        slm_overload = float(getText("What is the current SLM value?"))
                        slm_diff = slm_overload - slm_initial
                        uncertainty = 0.2
                        myclass = 1 if -1.8 <= slm_diff <= 1.8 else 2
                        return (slm_initial, atten_positive, slm_overload,
                                atten_overload, slm_diff, uncertainty, myclass)
                else:                         
                    atten -= step
                self.el100.set("%05.2f" % atten)

        self.wgenerator.positive_half_cycle(freq=4000, volt=target_volt/2.0)
        all_results = []
        row = _measure()
        all_results.append(row)
        print("initial SLM | atten | overload SLM | atten | diff SLM | uncertainty | class")
        print("   %.2f     %.2f      %.2f      %.2f       %.2f       %.2f       %d" % (
              row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
        self.wgenerator.turn_off()
        
        # TODO SET attenuator initial found value
        
        self.wgenerator.negative_half_cycle(freq=4000, volt=target_volt/2.0)
        row = _measure()
        all_results.append(row)
        self.wgenerator.turn_off()
        
        print("initial SLM | atten | overload SLM | atten | diff SLM | uncertainty | class")
        for row in all_results:
            print("   %.2f     %.2f      %.2f      %.2f       %.2f       %.2f     %d" % (
                  row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
        self.reset_instruments()
    
        # BUG SLM in table 1 larger by result
        # INFO:root:SET EL100 VALUE 15.10
        # initial SLM | atten | overload SLM | atten | diff SLM | uncertainty | class
        # 99.00     18.30      96.70      16.00       -2.30       0.20     2
        # 99.00     18.30      96.60      16.10       -2.40       0.20     2
    
    def peak_C_sound_level(self):
        """ISO61672-3 Paragraph 17
        Only for C-weighted sound level    NOTE C-weighting is Frequency Weighting option.
        Use least-sensitive sound range
        
        To set main variable = LCF in the SLM, do the following:
        measurement -> Edit display -> variable LAFMAX -> Edit field -> select from the list LAF
        -> Freq. Weighting button -> LCPeak or LCPeak max).  
        """
        self.reset_instruments()
        wtitle = "Peak C sound Level (61672-3 Electrical Tests Par.17)"
        lrange = self.conf.get('least_sensitive_level_range')
        upper_range = lrange[0]
        lower_range = lrange[1]
        weighting = "C"
        target_slm = upper_range - 8.0
        wait("Please set your Sound Level Meter to %s weighting, main variable LCF and the least sensitive level range (%g, %g)." % (
             weighting, upper_range, lower_range), title=wtitle)
        
        print("Peak C.    LCpeak-LC    Expected    SLM SLM  SLM    SLM    Deviation    Uncertainty    Class")
        print("Response                  (dB)       m1  m2   m3    avg       (dB)          (dB)") 
        
        def _measure_print(step, label, offset, target_volt):
            expected = target_slm + offset
            row = [label, offset,  expected]
            for _ in range(3):
                if step == 1:
                    self.wgenerator.start_burst(freq=8000, volt=target_volt,
                                                delay=0, count=1)
                elif step == 2:
                    self.wgenerator.positive_half_cycle(freq=500, volt=target_volt/2.0, # SOS
                                                        burst_count=1)
                elif step == 3:
                    self.wgenerator.negative_half_cycle(freq=500, volt=target_volt/2.0, # SOS
                                                        burst_count=1)
                self.wgenerator.stop_burst()
                self.wgenerator.turn_off()
                slm_val = float(getText("What is the SLM LCpeakMax value (dB)?"))                    
                row.append(slm_val)
                wait("Please reset your SLM.")
            slm_avg = (row[3] + row[4] + row[5]) / 3.0
            row.append(slm_avg)
            deviation = slm_avg - expected
            row.append(deviation)
            row.append(0.2) # uncertainty
            if step == 1:
                myclass = 1 if -1.4 < deviation < 1.4 else 2
            elif step == 2 or step == 3:
                myclass = 1 if -2.4 < deviation < 2.4 else 2
                    
            row.append(myclass)
            return row
        
        def _print_row(row):
            # TODO 2 decimal for SLM avg, deviation, uncertainty
            print("%s    %g    %g    %g    %g    %g    %g    %g    %g    %d" % (
                  row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7],
                  row[8], row[9]))
        
        all_results = []
        # Steady 8Khz tuning
        (target_volt, target_atten) = self._tune_wgenerator(8000, target_slm, wtitle)
        print("Attenuator setting %g dB." % target_atten)
        
        # Steady 8Khz measurement
        self.wgenerator.set_frequency(freq=8000, volt=target_volt)
        slm_val = float(getText("What is the SLM LCF value (dB)?"))
        print("Steady 8Khz    %g    %g" % (target_slm, slm_val))
        self.wgenerator.turn_off()
        wait("Please reset your SLM.")
        
        # Burst with 1 cycle, 8Khz
        row = _measure_print(step=1, label="1 cycle 8Khz    ", offset=3.4,
                             target_volt=target_volt)       
        all_results.append(row)
        _print_row(row)
        
        # Steady 500Hz tuning
        (target_volt, target_atten) = self._tune_wgenerator(500, target_slm, wtitle)
        print("Attenuator setting %g dB." % target_atten)
        
        # Steady 500Hz measurement
        self.wgenerator.set_frequency(freq=500, volt=target_volt)
        slm_val = float(getText("What is the SLM LCF value (dB)?"))
        print("Steady 500Hz    %g    %g" % (target_slm, slm_val))
        self.wgenerator.turn_off()
        wait("Please reset your SLM.")
        
        # Positive half cycle 500Hz
        row = _measure_print(step=2, label="Positive half cycle", offset=2.4,
                             target_volt=target_volt)
        all_results.append(row)
        _print_row(row)
                
        # Negative half cycle 500Hz
        row = _measure_print(step=3, label="Negative half cycle", offset=2.4,
                             target_volt=target_volt)
        all_results.append(row)
        _print_row(row)
        self.reset_instruments()
        
    def peak_response60651(self):
        """TODO peak response.
        """
        wtitle = "Peak Response, ISO61670"
        level_ranges = self.conf.get('level_ranges')
        upper_ref_level_range = level_ranges[0][0]
        lower_ref_level_range = level_ranges[0][1]
        weighting = "A"
        wait("Please set your Sound Level Meter REF level range (%g, %g) and %s weighting and press any key to continue." % (
             upper_ref_level_range, lower_ref_level_range, weighting), wtitle)
       
        slm_aim = upper_ref_level_range - 1.0        
        (volt, atten) = self._tune_wgenerator(2000, slm_aim, wtitle)
                
        self.wgenerator.set_frequency(2000, volt, shape='SIN')
        self.wgenerator.turn_on()
        slm_sin = float(getText("What is the SLM reading (dB)?"))
        self.wgenerator.turn_off()
        wait("Plase reset your SLM.")
        
        self.wgenerator.set_frequency(2000, volt, shape='RECT')
        self.wgenerator.turn_on()
        slm_square = float(getText("What is the SLM reading (dB)?"))
        self.wgenerator.turn_off()
                        
        # TODO for all types of instrument the test pulse shall produce
        # an indication no more than 2 dB below the indication
        # for the reference pulse
        print("Shape: SIN, SLM %g dB" % slm_sin)
        print("Shape: SQUARE, SLM %g dB" % slm_square)
        diff = slm_square - slm_sin
        pass_fail = "PASS" if abs(diff) < 2.0 else "FAIL"
        print("Difference: %g %s" % (diff, pass_fail))
        
    def toneburst_response(self):
        """ISO61672-3 Electrical Tests Par. 16      
        Continuous setting = LAF
        Fast setting = LAF MAX
        Slow setting = LAS MAX
        LA eq (equivalent)
        """
        self.reset_instruments()
        wtitle = "Toneburst Response, ISO61672-3 Electrical Tests Par. 16"
        level_ranges = self.conf.get('level_ranges')
        upper_ref_level_range = level_ranges[0][0]
        lower_ref_level_range = level_ranges[0][1]
        weighting = "A"
        wait("Please set your Sound Level Meter REF level range (%g, %g) and %s weighting and press any key to continue." % (
             upper_ref_level_range, lower_ref_level_range, weighting), wtitle)
       
        slm_aim = upper_ref_level_range - 3.0
        
        (volt, atten) = self._tune_wgenerator(4000, slm_aim, wtitle)   
    
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
                    self.wgenerator.start_burst(freq=4000, volt=volt,
                                                  delay=opt['delay'], count=opt['cycles'])
                    self.wgenerator.stop_burst()
                    self.wgenerator.turn_off()
                    slm_reading = float(getText("Voltage = %g. What is the SLM reading (dB)?" % volt))  # TODO which var?
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
        
        self.reset_instruments()
        
    def _tune_wgenerator(self, freq, target_slm, wtitle=None):
        """Tune Waveform Generator (Keysight / Agilent) voltage using a given
        frequency to achieve a target SLM measurement.
        Return voltage and attenuator values in a tuple.
        """
        self.wgenerator.set_frequency(freq=freq, volt=0.001)
        wait("Please tune first Waveform Generator voltage and then EL100 to achieve SLM %g dB." % target_slm,
             title=wtitle)
        volt = self.wgenerator.get_voltage()
        atten = self.el100.get()
        self.wgenerator.turn_off()
        return (volt, atten)
    
    def self_generated_noise_test(self):
        """Self-generated noise results BS7580, 5.5.2,  Part 1
        # dummy capacitor tolerance is +-20% of the micophone capacitor value.
        """
        wtitle = "Self-generated noise test (5.5.2 BS7580, Part 1)"
        wait("Please disconnect the microphone and connect the dummy transmitter (capacitator).",
             title=wtitle)
    
        weightings = ["A", "C", "Lin Wide"]
        for w in weightings:
            wait("Please use %s weighting." % w)
            res = []
            for _ in range(3):
                slm_val = float(getText("What is the SLM reading (dB)?",
                                        title=wtitle))
                res.append(slm_val)
                time.sleep(3)
            mean = (res[0] + res[1] + res[2]) / 3.0
            print("%s weighting. SLM measurements: %g    %g    %g    mean = %g (dB)" % (
                  w, res[0], res[1], res[2], mean))
    
    def time_averaging60651(self):
        """Time averaging TODO check with Yiannis
        """
        slm_type = self.conf.get('slm_type')
        self.reset_instruments(el100=99.00)
        slm_target = 90.0
        wait("Please configure your SLM to use Leq.")
        self.wgenerator.set_frequency(4000, volt=1.0)
        wait("Please configure the attenuator value so that SLM reads %g dB." % slm_target)
        ref_attenuation = self.el100.get()
        wait("Please reset your SLM.")
                        
        # TODO test frequency of 4kHz continuous
        self.wgenerator.set_frequency(4000, volt=1.0)
        slm_val1 = float(getText("What is the SLM reading (dB)?"))
        self.wgenerator.turn_off()
        wait("Please reset your SLM.")
        print("Generator: 4Khz, 1V, SLM Leq value=%g" % slm_val1)
        
        # 1ms toneburst for 60s
        self.wgenerator.start_burst(freq=2000, volt=1.0, delay=0, count=1)
        time.sleep(60)
        self.wgenerator.stop_burst()
        slm_val2 = float(getText("What is the SLM reading (dB)?"))
        diff2 = slm_val2 - slm_val1
        wait("Please reset your SLM.")
        print("Generator: 4Khz, 1V, burst 1ms, 60sec, SLM Leq value=%g, diff=%g" % (slm_val2, diff2))
        if slm_type == 0:
            print "PASS " if -0.5 <= diff2 <= 0.5 else "FAIL"
        elif slm_type == 1:
            print "PASS " if -1.0 <= diff2 <= 1.0 else "FAIL"
        else:
            print "PASS " if -1.5 <= diff2 <= 1.5 else "FAIL"
    
        # The amplitude of the continuous signal is 30 dB below the upper limit.
        
        # 1ms toneburst for 300s
        self.wgenerator.start_burst(freq=2000, volt=1.0, delay=0, count=1)
        time.sleep(300)
        self.wgenerator.stop_burst()
        slm_val3 = float(getText("What is the SLM reading (dB)?"))
        diff3 = slm_val3 - slm_val1
        wait("Please reset your SLM.")
        print("Generator: 4Khz, 1V, burst 1ms, 300sec, SLM Leq value=%g, diff=%g" % (slm_val3, diff3))
        print "PASS " if -1.0 <= diff3 <= 1.0 else "FAIL"
        
        # The amplitude of the continuous signal is 40 dB below the upper limit.

            
    def time_weighting60651(self):
        """Use LAFMAX SLM setting to keep SLM value in bursts.
        """
        
        def _pass_fail(slm_type, diff, weighting):
            """table Page 15 of 42, The verification of SLM to BS7580.
            """
            if weighting == "F":
                diff -= 1.0
                if slm_type == 0:   
                    return "PASS" if -0.5 <= diff <= 0.5 else "FAIL"
                elif slm_type == 1:
                    return "PASS" if -1.0 <= diff <= 1.0 else "FAIL"
                elif slm_type == 2:
                    return "PASS" if -2.0 <= diff <= 1.0 else "FAIL"
                elif slm_type == 3:
                    return "PASS" if -3.0 <= diff <= 1.0 else "FAIL"
                
            elif weighting == "S":
                diff -= 4.1
                if slm_type == 0:   
                    return "PASS" if -0.5 <= diff <= 0.5 else "FAIL"
                elif slm_type == 1:
                    return "PASS" if -1.0 <= diff <= 1.0 else "FAIL"
                elif slm_type == 2:
                    return "PASS" if -2.0 <= diff <= 2.0 else "FAIL"
                elif slm_type == 3:
                    return "PASS" if -2.0 <= diff <= 2.0 else "FAIL"
                
            elif weighting == "I1":
                diff -= 8.8
                if slm_type == 0 or slm_type == 1:   
                    return "PASS" if -2.0 <= diff <= 2.0 else "FAIL"
                elif slm_type == 2:
                    return "PASS" if -3.0 <= diff <= 3.0 else "FAIL"
            elif weighting == "I2":
                diff -= 2.7
                if slm_type == 0 or slm_type == 1:   
                    return "PASS" if -1.0 <= diff <= 1.0 else "FAIL"
                elif slm_type == 2:
                    return "PASS" if -2.0 <= diff <= 2.0 else "FAIL"            
        
        self.reset_instruments(el100=99.00)
        target_slm = self.conf.get('linear_operating_range').get("max") - 4.0
                    
        """ FAST """
        
        wtitle = "Time Weighting (Fast)"
        wait("Please configure your SLM to FA weighting.", title=wtitle)
        (target_volt, target_atten) = self._tune_wgenerator(2000, target_slm, wtitle)
        self.wgenerator.turn_off()
        wait("Please reset your SLM.")
        
        res = []
        for _ in range(3):
            # send burst
            self.wgenerator.start_burst(freq=2000, volt=target_volt, delay=0, count=200)
            slm_fast_burst = float(getText("What is the SLM reading (dB)?", title=wtitle))
            self.wgenerator.stop_burst()
            res.append(slm_fast_burst)
            wait("Please reset your SLM.")
        
        print("Time Weighting Fast Continuous SLM=%g dB, attenuator %g dB" % (
              target_slm, target_atten))
        res_avg = sum(res) / 3.0
        pass_fail = _pass_fail(self.conf.get('slm_type'), res_avg - target_slm, "F")
        print("Burst: %g %g %g dB, Average: %g %s" % (res[0], res[1], res[2], res_avg, pass_fail))
        
        """ SLOW """
        
        wtitle = "Time Weighting (Slow)"
        wait("Please configure your SLM to SA weighting.", title=wtitle)
        (target_volt, target_atten) = self._tune_wgenerator(2000, target_slm, wtitle)
        self.wgenerator.turn_off()
        wait("Please reset your SLM.")
        
        res = []
        for _ in range(3):
            # send burst
            self.wgenerator.start_burst(freq=2000, volt=target_volt, delay=0, count=500)
            slm_fast_burst = float(getText("What is the SLM reading (dB)?", title=wtitle))
            self.wgenerator.stop_burst()
            res.append(slm_fast_burst)
            wait("Please reset your SLM.")
        
        print("Time Weighting Slow Continuous SLM=%g dB, attenuator %g dB" % (
              target_slm, target_atten))
        res_avg = sum(res) / 3.0
        pass_fail = _pass_fail(self.conf.get('slm_type'), res_avg - target_slm, "F")
        print("Burst: %g %g %g dB, Average: %g %s" % (res[0], res[1], res[2], res_avg, pass_fail))
                
        """ Impulse Single Burst - two test signals are used for this."""
        
        wtitle = "Time Weighting (Impulse)"
        wait("Please configure your SLM to Impulse A weighting.", title=wtitle)
        (target_volt, target_atten) = self._tune_wgenerator(2000, target_slm, wtitle)
        self.wgenerator.turn_off()
        wait("Please reset your SLM.")
        
        res = []
        for _ in range(3):
            self.wgenerator.start_burst(freq=2000, volt=target_volt, delay=0, count=5)
            slm_impulse_burst = float(getText("What is the SLM reading (dB)?", title=wtitle))
            self.wgenerator.stop_burst()
            res.append(slm_impulse_burst)
            wait("Please reset your SLM.")
        
        res2 = []
        for _ in range(3):
            self.wgenerator.start_burst(freq=100, volt=target_volt, delay=0, count=5)
            slm_impulse_burst = float(getText("What is the SLM reading (dB)?", title=wtitle))
            self.wgenerator.stop_burst()
            res2.append(slm_impulse_burst)
            wait("Please reset your SLM.")
        
        print("Time Weighting Impulse Continuous SLM=%g dB, attenuator %g dB" % (
              target_slm, target_atten))
        res_avg2 = sum(res2) / 3.0
        pass_fail = _pass_fail(self.conf.get('slm_type'), res_avg - target_slm, "I1")
        print("2000Hz Burst: %g %g %g dB, Average: %g %s" % (res[0], res[1], res[2], res_avg, pass_fail))
        pass_fail = _pass_fail(self.conf.get('slm_type'), res_avg2 - target_slm, "I2")
        print("100Hz Burst: %g %g %g dB, Average: %g %s" % (res2[0], res2[1], res2[2], res_avg2, pass_fail))
        
        self.reset_instruments()
            
    def pulse_range_sound_exposure_level_and_overload60651(self):
        """Continuous level set up to 50dB
        50 dB not attenable therefore set up to 50.1 dB
        Attenuator reading = 58.55
        Channel 1 reconnect and adjusted to read 108 dB
            40 cycle bursts applied. Slm set to Leq and reset.
        SLM reading after 10s = 78.2 78.2 78.2 dB
        Nominal Reading = 78 dB
        """
        wtitle = "Pulse Range Sound Exposure Level & Overload (Subclauses 5.5.10, 5.5.11 and 5.5.12 of BS 7580: Part 1)."
        target_slm = 50
        (target_volt, target_atten) = self._tune_wgenerator(1000, target_slm, wtitle)
        # TODO what reconnect & adjusted means?
        # TODO 
        
        """Sound exposure test
        40 cycle burst applied to SLM. set to SEL and reset.
        SLM reading = 87.8 87.8 87.8
        Nominal Reading = 88 dB
        """
        wait("Please set your SLM to SEL and reset.")
        self.wgenerator.start_burst(freq=1000, volt=target_volt, delay=0, count=40)
        res = []
        for _ in range(3):
            slm_val = float(getText("What is the SLM reading (dB)?", title=wtitle))
            res.append(slm_val)
            time.sleep(3)
        self.wgenerator.stop_burst()
        slm_mean = (res[0] + res[1] + res[2]) / 3.0
        
        print("%d cycle burst applied to SLM.")
        print("SLM readings: %g %g %g dB" % ( res[0], res[1], res[2]))
        print("Nominal Reading = %g dB" % 9999)
        # TODO what is the nominal reading?
        
        """Overload test (Integrating Mode)
        Output level of PM5138A adjusted until overload, the decreased by 1 dB.
        Corresponding continuous reading = 120.4 dB
        4 cycle burst applied, SLM set LEQ and reset
        SLM reading after 10 s = 80.7 80.7 80.7 dB
        Nominal Reading = 80.4 dB)
        """
        
    def rms_accuracy_and_overload60651(self):
        # TODO run with Yiannis
        
        # TODO page 16 of 42 The verification of SLM to BS7580
        # The toneburst consists of 11 cycles of a sine wave of frequency 2 kHz
        # with a repetition frequency of 40 Hz and having an RMS level which is
        # identical to that of the continuous sine wave signal.
        self.reset_instruments()
        #lrange = self.conf.get('least_sensitive_level_range')
        #upper_range = lrange[0]
        #lower_range = lrange[1]
        upper_range = 120
        lower_range = 40

        target_slm = upper_range - 2
               
        wtitle = "RMS Accuracy and Overload"                
        wait("Please set your Sound Level Meter REF level range (%g, %g) and A weighting and press any key to continue." % (
             upper_range, lower_range), title=wtitle)

        self.el100.set(20.00) # Must start with a high value and the decrease it
        slm_initial = upper_range - 1
        (target_volt, atten_positive) = self._tune_wgenerator(2000, target_slm, wtitle)
        
        atten = atten_positive
        step = 0.5
        switch_step = True
        results = []
        while(True):
            self.wgenerator.start_burst(freq=2000, volt=target_volt, delay=0, count=11)
            answer = getText("Do we have an overload in the Sound Level Meter? (y / n)").lower()
            
            if answer == "y":
                if step == 0.5:
                    step = 0.1
                    logging.info("Switching to step 0.1")
                elif step == 0.1:
                    # When we switch from 0.5 to 0.1, we go back 0.5. This happens only once.
                    if switch_step:
                        atten += 1.0
                        switch_step = False
                        
                    atten_overload = atten
                    slm_overload = float(getText("What is the current SLM value?"))
                    slm_diff = slm_overload - slm_initial
                    uncertainty = 0.2
                    myclass = 1 if -1.8 <= slm_diff <= 1.8 else 2   # TODO change this
                    results.append((slm_initial, atten_positive, slm_overload,
                                    atten_overload, slm_diff, uncertainty, myclass))
                    break
                    # TODO BUG not breaking here.
            else:                         
                atten -= step
            self.wgenerator.stop_burst()
            self.el100.set(atten)

        # reducing the signal level by 1 dB
        atten -= 1.0
        self.wgenerator.start_burst(freq=2000, volt=target_volt, delay=0, count=11)
        slm_overload = float(getText("What is the current SLM value?"))
        slm_diff = slm_overload - slm_initial
        uncertainty = 0.2
        myclass = 1 if -1.8 <= slm_diff <= 1.8 else 2   # TODO change this
        results.append((slm_initial, atten_positive, slm_overload,
                        atten_overload, slm_diff, uncertainty, myclass))
        self.wgenerator.stop_burst()
        
        # reducing the signal level by a further 3 dB
        atten -= 3
        self.wgenerator.start_burst(freq=2000, volt=target_volt, delay=0, count=11)
        slm_overload = float(getText("What is the current SLM value?"))
        slm_diff = slm_overload - slm_initial
        uncertainty = 0.2
        myclass = 1 if -1.8 <= slm_diff <= 1.8 else 2   # TODO change this
        results.append((slm_initial, atten_positive, slm_overload,
                        atten_overload, slm_diff, uncertainty, myclass))
        self.wgenerator.stop_burst()

        print("initial SLM | atten | overload SLM | atten | diff SLM | uncertainty | class")
        for row in results:
            print("   %.2f     %.2f      %.2f      %.2f       %.2f       %.2f       %d" % (
                row[0], row[1], row[2], row[3], row[4], row[5], row[6]))       
    
        self.reset_instruments()