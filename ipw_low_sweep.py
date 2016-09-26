#!/usr/bin/env python
###################################
# ipw_low_sweep.py
#
# Runs equivalent scan to LABView IPW
# low 10 step.  Outputs a waveform
# for each scan, including precursor
# noise information (to ensure offset
# is correct when integrating).
#
# Note that the rate is fixed (1 kHz)
#
###################################

import os
import sys
import optparse
import time
import sweep
import scopes
import scope_connections
import utils

if __name__=="__main__":
    parser = optparse.OptionParser()
    parser.add_option("-b",dest="box",help="Box number (1-12)")
    parser.add_option("-c",dest="channel",help="Channel number (1-8)")
    parser.add_option("-x",dest="cutoff",help="Cutoff (IPW) from Ref sweep (runs -1500 -> +500 of this value)")
    (options,args) = parser.parse_args()

    #Time
    total_time = time.time()
    
    #Set passed TELLIE parameters
    box = int(options.box)
    channel = int(options.channel)
    cutoff = int(options.cutoff)

    #Fixed parameters
    delay = 1.0 # 1ms -> kHz

    #run the initial setup on the scope
    usb_conn = scope_connections.VisaUSB()
    scope = scopes.Tektronix3000(usb_conn)
    ###########################################
    scope_chan = 4 # We're using channel 1!
    termination = 50 # Ohms
    trigger_level = 0.5 # half peak minimum
    falling_edge = True
    min_trigger = -0.004
    y_div_units = 1 # volts
    x_div_units = 4e-9 # seconds
    y_offset = -2.5*y_div_units # offset in y (2.5 divisions up)
    x_offset = +2*x_div_units # offset in x (2 divisions to the left)
    record_length = 1e3 # trace is 100e3 samples long
    half_length = record_length / 2 # For selecting region about trigger point
    ###########################################
    scope.unlock()
    scope.set_active_channel(scope_chan)
    #Turn off channel 1
    scope.set_active_channel(1,active=False)
    scope.set_horizontal_scale(x_div_units)
    scope.set_horizontal_delay(x_offset) #shift to the left 2 units
    scope.set_channel_y(scope_chan, y_div_units, pos=2.5)
    scope.set_display_y(scope_chan, y_div_units, offset=y_offset)
    scope.set_channel_termination(scope_chan, termination)
    scope.set_single_acquisition() # Single signal acquisition mode
    scope.set_record_length(record_length)
    scope.set_data_mode(half_length-50, half_length+50)
    scope.lock()
    scope.begin() # Acquires the pre-amble! 


    #Create a new, timestamped, summary file
    timestamp = time.strftime("%y%m%d_%H.%M",time.gmtime())
    sweep.check_dir('./MasterMode/low_intensity')
    saveDir = sweep.check_dir("./MasterMode/low_intensity/Box_%02d/" % (box))
    output_filename = "%s/Chan%02d_IPWlow_%s.dat" % (saveDir,channel,timestamp)
    #results = utils.PickleFile(output_filename, 1)
    
    output_file = file(output_filename,'w')
    output_file.write("#PWIDTH\tPWIDTH Error\tPIN\tPIN Error\tWIDTH\tWIDTH Error\tRISE\tRISE Error\tFALL\tFALL Error\tAREA\tAREA Error\tMinimum\tMinimum Error\n")

    #Start scanning!
    tmpResults = {}
    tmpResults["peak"] = -1.0
    widths = [int(options.cutoff)]
    t_start = time.time()
    while tmpResults["peak"] < -0.05:
        widths.append(widths[-1]+50)
	width = widths[-1]
        min_volt = None
        loopStart = time.time()
        if tmpResults!=None:
            #set a best guess for the trigger and the scale
            #using the last sweeps value
            min_volt = float(tmpResults["peak"])
            if min_volt == 0: # If bad data set, make none
                min_volt = 50e-3 # Used to be None - Changed for speed-up!
        tmpResults = sweep.sweep(saveDir,box,channel,width,delay,scope,scope_chan,min_volt)
                
        output_file.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n"%(width, 0,
                                            tmpResults["pin"], tmpResults["pin error"],
                                            tmpResults["width"], tmpResults["width error"],
                                            tmpResults["rise"], tmpResults["rise error"],
                                            tmpResults["fall"], tmpResults["fall error"],
                                            tmpResults["area"], tmpResults["area error"],
                                            tmpResults["peak"], tmpResults["peak error"] ))

        print "WIDTH %d took : %1.1f s" % (width, time.time()-loopStart)

    output_file.close()

    print "Total script time : %1.1f mins"%( (time.time() - total_time) / 60)
    
