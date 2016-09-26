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
import numpy as np
#
import plot_ipw
import calc_response
import sweep
import scopes
import scope_connections
import utils


def calc_low_sweep_range(box, channel):
    """Use the results from the most recent broad sweep file to calculate the
    range of interest. 
    """
    files = calc_response.return_files("./broad_sweep", box)
    fname = None
    for file in files:
        if "Chan%02d" % channel in file:
            fname = file
            break
    results = plot_ipw.read_scope_scan(fname)
    
    photons = np.zeros(len(results))
    for i in range(len(results)):
        photons[i] = plot_ipw.get_photons(results[i]["area"], 0.5)
    idx = np.where( photons < 1e5 )[0][0] - 1
    width_thresh = results[idx]["ipw"]
    return range(width_thresh, width_thresh+1600, 25)

def calc_start_ipw(box,channel):
    return calc_low_sweep_range(box,channel)[0]

if __name__=="__main__":
    parser = optparse.OptionParser()
    parser.add_option("-b",dest="box",type=int,help="Box number (1-12)")
    parser.add_option("-c",dest="channel",type=int,help="Channel number (1-8)")
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
    trig_chan = 1 # Which channel is the trigger in?
    pmt_chan = 4 # Which channel is the pmt in?
    termination = 50 # Ohms
    trigger_level = 0.5 # half peak minimum
    falling_edge = True
    min_trigger = -0.004
    y_div_units = 1 # volts
    x_div_units = 100e-9 # seconds
    #y_offset = -2.5*y_div_units # offset in y (2.5 divisions up)
    y_offset = 0.5*y_div_units # offset in y (for UK scope)
    x_offset = +3*x_div_units # offset in x (2 divisions to the left)
    record_length = 100e3 # trace is 1e3 samples long
    half_length = record_length / 2 # For selecting region about trigger point
    ###########################################
    scope.unlock()
    scope.set_horizontal_scale(x_div_units)
    scope.set_horizontal_delay(x_offset) #shift to the left 3 units
    scope.set_active_channel(trig_chan)
    scope.set_active_channel(pmt_chan)
    scope.set_channel_y(trig_chan, y_div_units, pos=-3)
    scope.set_channel_y(pmt_chan, y_div_units, pos=3)
    scope.set_channel_termination(trig_chan, termination)
    scope.set_channel_termination(pmt_chan, termination)
    scope.set_single_acquisition() # Single signal acquisition mode
    scope.set_record_length(record_length)
    scope.set_data_mode(half_length-800, half_length+300)
    scope.set_edge_trigger(1, trig_chan, falling=False)
    scope.lock()
    scope.begin() # Acquires the pre-amble! 

    #Create a new, timestamped, summary file
    timestamp = time.strftime("%y%m%d_%H.%M",time.gmtime())
    sweep.check_dir('./low_intensity')
    saveDir = sweep.check_dir("low_intensity/Box_%02d/" % (box))
    output_filename = "%s/Chan%02d_IPWlow_%s.dat" % (saveDir,channel,timestamp)
    #results = utils.PickleFile(output_filename, 1)
    
    output_file = file(output_filename,'w')
    output_file.write("#PWIDTH\tPWIDTH Error\tPIN\tPIN Error\tWIDTH\tWIDTH Error\tRISE\tRISE Error\tFALL\tFALL Error\tAREA\tAREA Error\tMinimum\tMinimum Error\tTime\tTime Error\n")
    firstIter = True
    #Start scanning!
    tmpResults = {}
    t_start = time.time()
    tmpResults["peak"] = -1.0
    widths = [int(options.cutoff)]
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
        tmpResults = sweep.sweep(saveDir,box,channel,width,delay,scope,trig_chan,pmt_chan,min_volt=min_volt)                
        # Write results to file
	output_file.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n"%(width, 0,
                                            tmpResults["pin"], tmpResults["pin error"],
                                            tmpResults["width"], tmpResults["width error"],
                                            tmpResults["rise"], tmpResults["rise error"],
                                            tmpResults["fall"], tmpResults["fall error"],
                                            tmpResults["area"], tmpResults["area error"],
                                            tmpResults["peak"], tmpResults["peak error"],
                                            tmpResults["time"], tmpResults["time error"]))

        print "WIDTH %d took : %1.1f s" % (width, time.time()-loopStart)

    # Close file and exit
    output_file.close()
    print "Total script time : %1.1f mins"%( (time.time() - total_time) / 60)
    
