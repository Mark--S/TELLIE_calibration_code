#!/usr/bin/env python
#########################
# sweep.py
#  Generic module for running
# IPW sweeps with Tek scope
#
#########################
import os
from core import serial_command
from common import comms_flags
import math
import time
#try:
import utils
#except:
#    pass
import sys
import readPklWaveFile
import calc_utils as calc
import numpy as np
#import matplotlib.pyplot as plt

port_name = "/dev/tty.usbserial-FTE3C0PG"
#port_name = "/dev/tty.usbserial-FTGA2OCZ"
## TODO: better way of getting the scope type
scope_name = "Tektronix3000"
_boundary = [0,1.5e-3,3e-3,7e-3,15e-3,30e-3,70e-3,150e-3,300e-3,700e-3,1000]
#_v_div = [1e-3,2e-3,5e-3,10e-3,20e-3,50e-3,100e-3,200e-3,500e-3,1.0]
#_v_div_1 = [1e-3,2e-3,5e-3,10e-3,20e-3,50e-3,100e-3,200e-3,500e-3,1.0,2.0]
_v_div = np.asarray([20e-3, 50e-3, 100e-3, 200e-3, 500e-3, 1, 2, 10]) # For scope at sussex
_v_div_1 = np.asarray([20e-3, 50e-3, 100e-3, 200e-3, 500e-3, 1, 2])

sc = None
sc = serial_command.SerialCommand(port_name)

pulse_edge = None

#initialise sc here, faster options setting
def start():
    global sc
    sc = serial_command.SerialCommand(port_name)

def set_port(port):
    global port_name
    port_name = port

def set_scope(scope):
    global scope_name
    if scope=="Tektronix3000" or scope=="LeCroy":
        scope_name = scope
    else:
        raise Exception("Unknown scope")

def check_dir(dname):
    """Check if directory exists, create it if it doesn't"""
    direc = os.path.dirname(dname)
    try:
        os.stat(direc)
    except:
        os.makedirs(direc)
        print "Made directory %s...." % dname
    return dname    

def return_zero_result():
    r = {}
    r['pin'], r['pin error'] = 0, 0
    r['width'], r['width error'] = 0, 0
    r['rise'], r['rise error'] = 0, 0
    r['fall'], r['fall error'] = 0, 0
    r['area'], r['area error'] = 0, 0
    r['peak'], r['peak error'] = 0, 0
    r['time'], r['time error'] = 0, 0
    return r

def save_scopeTraces(fileName, scope, channels, noPulses):
    """Save a number of scope traces to file - uses compressed .pkl"""
    scope._get_preamble(channels[0])
    results = utils.PickleFile(fileName, channels)
    results.add_meta_data("timeform_1", scope.get_timeform(channels[0]))

    #ct = scope.acquire_time_check()
    #if ct == False:
    #    print 'No triggers for this data point. Will skip and set data to 0.'
    #    results.save()
    #    results.close()
    #    return False

    t_start, loopStart = time.time(),time.time()
    for i in range(noPulses):
        try:
    	    for chan in channels:
	        results.add_data(scope.get_waveform(chan), chan)
        except Exception, e:
            print "Scope died, acquisition lost."
            print e
        if i % 100 == 0 and i > 0:
            print "%d traces collected - This loop took : %1.1f s" % (i, time.time()-loopStart)
            loopStart = time.time()
    print "%d traces collected TOTAL - took : %1.1f s" % (i, (time.time()-t_start))
    results.save()
    results.close()
    return True

def find_and_set_scope_y_scale(trig_chan, pmt_chan, scope, scaleGuess=None):
    """Finds best y_scaling for the current IPW settings
    """
    func_time = time.time()
    sc.fire_continuous()
    time.sleep(0.1)

    # Trigger off trigger signal
    scope.set_edge_trigger(0.5, trig_chan, falling=False)
    # Set scale. If we have a guess, use it. Else go for the largest.
    #if scaleGuess:
    #    print _v_div, np.abs(scaleGuess)
    #    index = np.where(_v_div > np.abs(scaleGuess))[0][0]
    #    print index, _v_div[index]
    #    scope.set_channel_y(pmt_chan, _v_div[index], pos=3)
    #else:
    #scope.set_channel_y(pmt_chan, _v_div[-1], pos=3)     

    time.sleep(1.0) # Need to wait for scope to recognise new settings
    scope._get_preamble(pmt_chan)

    # Calc min value
    mini, wave = np.zeros( 10 ), None    
    for i in range( len(mini) ):
        # Check we get a trigger - even at the lowest setting we might see nothing
        ct = scope.acquire_time_check(timeout=1.)
        if ct == False:
            print 'Triggers missed for this data point. Will skip and set data to 0.'
            return False
        wave = scope.get_waveform(pmt_chan)
        mini[i] = min(wave) - np.mean(wave[0:1000])
    min_volt = np.mean(mini)
    print "MINIMUM MEASUREMENT:", min_volt
    if np.abs(min_volt) < 0.006:
        return False

    # Calculate appropriate scope scale
    if -1*(min_volt/6) > _v_div_1[-1]:
        scale = _v_div_1[-1]
    else: 
        scale_idx = np.where( np.array(_v_div_1) >= -1*(min_volt/6) )[0][0]
        scale = _v_div_1[scale_idx]
    if scale == 2e-3:
        trig = -4e-3
    elif scale == 1e-3:
        trig = -3e-3
    else:
        trig = -1.*scale
    print "Preticted scale = %1.3fV, actual scale = %1.3fV" % (-1*(min_volt/6.6), scale)
    
    # Set scale and return
    scope.set_channel_y(pmt_chan, scale, pos=3) # set scale, starting with largest
    time.sleep(1.0) # Need to wait for scope to recognise new settings
    scope._get_preamble(pmt_chan)
    print "TOTAL FUNC TIME = %1.2f s" % (time.time() - func_time)
    sc.stop()
    return True

def read_pin():
    '''Wait keep looking for pin. It will be retuned when the sequence ends
    '''
    pin, rms = None, None
    try:
        while (pin == None):
            pin, rms, channel = sc.read_pin_sequence()
    except KeyboardInterrupt:
        print "Keyboard interrupt"
    return int(pin), float(rms)

def printParamsDict(dict, name):
    """Print calculated parameters and print to screen"""
    area, areaStd =dict["area"], dict["area error"]
    rise, riseStd =dict["rise"], dict["rise error"]
    fall, fallStd =dict["fall"], dict["fall error"]
    width, widthStd= dict["width"], dict["width error"]
    peak, peakStd =dict["peak"], dict["peak error"]
    time, timeStd =dict["time"], dict["time error"]
    pin, pinStd =dict["pin"], dict["pin error"]

    print "%s:" % name
    print "--------"
    print "Pin  \t\t= %1.2f +/- %1.2f " % (pin, pinStd)
    print "-"
    print "Peak \t\t= %1.2f +/- %1.2f V" % (peak, peakStd)
    print "Area \t\t= %1.2e +/- %1.2e Vs" % (area, areaStd)
    print "Fall time \t= %1.2f +/- %1.2f ns" % (fall*1e9, fallStd*1e9)
    print "Rise time \t= %1.2f +/- %1.2f ns" % (rise*1e9, riseStd*1e9)
    print "Width \t\t= %1.2f +/- %1.2f ns" % (width*1e9, widthStd*1e9)
    print "-"
    print "Pulse sep \t= %1.2f +/- %1.2f ns" % (time*1e9, timeStd*1e9)

def find_pulse(x, y, step_back = 500, step_forward = 500):
    """Use differential to find the PMT pulse in the long trace"""
    global pulse_edge
    if pulse_edge == None:
        pulse_edge = np.where(y[1,:] < -0.1)[0][0]
        print pulse_edge
    return x[pulse_edge-step_back:pulse_edge+step_forward], y[:,pulse_edge-step_back:pulse_edge+step_forward]

def sweep(dir_out,box,channel,width,delay,scope,trig_channel,pmt_channel,min_volt=None):
    """Perform a measurement using a default number of
    pulses, with user defined width, channel and rate settings.
    """
    print '____________________________'
    print width

    #fixed options
    height = 16383    
    fibre_delay = 0
    trigger_delay = 0
    pulse_number = 1000
    #first select the correct channel and provide settings
    logical_channel = (box-1)*8 + channel
    
    sc.select_channel(logical_channel)
    sc.set_pulse_width(width)
    sc.set_pulse_height(16383)
    sc.set_pulse_number(pulse_number)
    sc.set_pulse_delay(delay)
    sc.set_fibre_delay(fibre_delay)
    sc.set_trigger_delay(trigger_delay)
    
    # first, run a single acquisition with a forced trigger, effectively to clear the waveform
    scope._connection.send("trigger:state ready")
    time.sleep(0.1)
    scope._connection.send("trigger force")
    time.sleep(0.1)

    # Get pin read
    sc.fire_sequence() # previously fire_sequence!
    #wait for the sequence to end
    tsleep = pulse_number * (delay*1e-3 + 210e-6)
    time.sleep(tsleep) #add the offset in
    time.sleep(0.1)
    pin, rms = read_pin()
    print "PIN (sweep):", pin, rms
    sc.stop()

    # File system stuff
    check_dir("%s/raw_data/" % (dir_out))
    directory = check_dir("%s/raw_data/Channel_%02d/" % (dir_out,logical_channel))
    fname = "%sWidth%05d" % (directory,width)
    
    # Check scope
    ck = find_and_set_scope_y_scale(trig_channel, pmt_channel, scope, scaleGuess=min_volt)
    if ck == True:
        print "Saving raw files to: %s..." % fname
        sc.fire_continuous()
        time.sleep(0.2)
        save_ck = save_scopeTraces(fname, scope, [trig_channel,pmt_channel], 100)
        sc.stop()
        if save_ck == True:
            # Calc and return params
            x1,y1 = calc.readPickleChannel(fname, trig_channel,[trig_channel,pmt_channel])
            x2,y2 = calc.readPickleChannel(fname, pmt_channel,[trig_channel,pmt_channel])
            #x2,y2 = find_pulse(x2,y2)
            calc.plot_eg_pulses(x2, y2, 10, fname='%s/LastMeasuredPulses.png' % dir_out.split("/")[0])
            #os.system("open %s/LastMeasuredPulses.png" % dir_out.split("/")[0])
            # Make sure we see a signal well above noise
            snr = calc.calcSNR(x2, y2)
            print "SNR: ", snr
            if snr > 7:
                # Calculate results
                results = calc.dictionary_of_params(x2,y2)
                mean, std, sterr = calc.calcJitter(x2, y2, x1, y1, threshold=0.4)
                results["time"] = mean
                results["time error"] = std
                results["pin"] = pin
                results["pin error"] = rms
                printParamsDict(results, width)
            else:
                # No signal observerd, return zero
                results = return_zero_result()
                results['pin'] = pin
                results['pin error'] = rms
        elif save_ck == False:
            # Data acquisition was not sucessful, return zero
            results = return_zero_result()
            results['pin'] = pin
            results['pin error'] = rms
    else: 
        # Couldn't find y scaling, return zero
        results = return_zero_result()
        results['pin'] = pin
        results["pin error"] = rms
    sc.stop()
    return results
