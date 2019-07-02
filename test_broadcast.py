# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 17:16:56 2019

@author: seidi
"""

# Default
import socket
import sys
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import time
import math
import threading
import struct

# Installed with pip
import re

#selecting the right backend, change qt4agg to your desired backend
# =============================================================================
# matplotlib.use('qt4agg')
# =============================================================================

# Open config file txt
configFile         = open('configFile.txt', 'r+') 
configFileText     = configFile.read()
parameters = []
for line in configFileText.split('\n'):
    if not re.findall('((^#))', line):
      parameters.append(line)
parameters = list(filter(None, parameters))
parameters = '\n'.join(parameters)
print(parameters)

BYTE_SIZE        = 8

# =============================================================================
# Streaming Parameters
# =============================================================================
SERVER_IP_Str = re.findall('SERVER_IP\s*=\s*(\d+.\d+.\d+.\d+)',parameters)
SOCKET_Str    = re.findall('SOCKET\s*=\s*(\d*)',parameters)

TCP_IP = SERVER_IP_Str[0]
SOCKET  = int(SOCKET_Str[0])

# =============================================================================
# OpenVibe Parameters
# =============================================================================
ACQUISITION_FREQ_Str = re.findall('ACQUISITION_FREQ\s*=\s*(\d*)',parameters)
EPOCHS_Str           = re.findall('EPOCHS\s*=\s*(\d*)',parameters)
CHANNELS_Str         = re.findall('CHANNELS\s*=\s*(\d*)',parameters)

ACQUISITION_FREQ = int(ACQUISITION_FREQ_Str[0])
epochs           = int(EPOCHS_Str[0])
nbchannels       = int(CHANNELS_Str[0])

# =============================================================================
# Visualization Parameters
# =============================================================================
WINDOW_Str  = re.findall('WINDOW\s*=\s*(\d*)',configFileText)
DO_FFT_Str  = re.findall('DO_FFT\s*=\s*(\d*)',configFileText)

WINDOW_SEC   = int(WINDOW_Str[0])
WINDOW_RANGE = WINDOW_SEC*ACQUISITION_FREQ # points
BUFFER_SIZE  = nbchannels*epochs*BYTE_SIZE # Buffer holds the whole TCP package
do_fft       = int(DO_FFT_Str[0])          # Control flag

# =============================================================================
# Init data matrices and vectors
# =============================================================================
x_vec           = np.linspace(0,1,WINDOW_RANGE+1)[0:-1]
xaxis_vector    = np.empty(len(x_vec))
xaxis_vector[:] = np.nan

f_axis = np.linspace(0, ACQUISITION_FREQ, WINDOW_RANGE//2)

# line will hold a pointer to each subplot
line1 = []
line2 = []
    
# Matrix to store EEG data
channelsData = []
fftData = []
for chann in range(0,nbchannels):
    channelsData.append(np.empty(len(x_vec)))
    fftData.append(np.empty(WINDOW_RANGE//2))
    
# Global control flags
run = False
calculate_fft_now = False

def on_click(event):
    global run
    if event.dblclick:
         run = False       

def data_listener():    
    global run
    # Create a TCP/IP socket
    sock_data = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Bind the socket to the address TCP_IP
    server_data_adr = (TCP_IP, SOCKET)
        
    while not run:        
        try:
            print(sys.stderr, 'connecting to %s port %s' % server_data_adr)
            sock_data.connect(server_data_adr)
            print('\nConnected!\n\n')
            run = True
        except:            
            print("Couldn't connect to IP",TCP_IP,'socket',SOCKET)
            run = False
            break
    
    while run:
        try:        
            while True:
                curr_data = sock_data.recv(BUFFER_SIZE)
                
                if len(curr_data) == BUFFER_SIZE:
                    endBuff = int(BUFFER_SIZE/(BYTE_SIZE*nbchannels))
                    
                    # Break TCP datagram apart to gather streamed data
                    for chann in range(0,nbchannels):                    
                        startOffset = BYTE_SIZE*epochs*chann
                        for buff in range(0,endBuff):
                            new_val  = struct.unpack('d', curr_data[startOffset:startOffset+BYTE_SIZE])[0]
                            channelsData[chann][-1] = new_val   
                            channelsData[chann] = np.append(channelsData[chann][1:],0.0) 

                            startOffset += BYTE_SIZE
        except:
            print('No Data Available')
    
    print('\n\nClosing sockets')
    sock_data.close()

def calculate_fft():
    global calculate_fft_now
    while True:
        if calculate_fft_now:
            for chann in range(0,nbchannels):
                n = len(channelsData[chann])        # length of the signal
                Y = np.fft.fft(channelsData[chann]) # fft computing
                fftData[chann] = abs(Y[range(n//2)])/n
                calculate_fft_now = False
        else:
            time.sleep(0.04)
                

def live_plotter():    
    global calculate_fft_now
                
    for chann in range(0,nbchannels):
        if do_fft:            
            # Update FFT Y Axis      
            line2[chann][0].set_ydata(fftData[chann])
            calculate_fft_now = True
        
        # Update Raw Data Y Axis
        line1[chann][0].set_ydata(channelsData[chann])
        
    # this pauses the data so the figure/axis can catch up - the amount of pause can be altered above
    plt.pause(0.001)

def main():
    global run
    
    # Create thread for data listening and start it right away
    # A daemon thread will be forced to close when the program ends
    thread_data = threading.Thread(target = data_listener, daemon = True)
    thread_data.start()
    time_to_try = 30
    start_try = time.time()
    
    while not run:
        time.sleep(2)  
        if time.time() - start_try > time_to_try:
            break
        elif run == True:
            break            
        
    if run:
        if line1==[]:
            # this is the call to matplotlib that allows dynamic plotting
            plt.ion()            
            
            # Adjust figure size according to nb of channels
            if nbchannels < 6:
                fig_height = 400
            elif nbchannels > 10:
                fig_height = 900
            else:
                fig_height = nbchannels*0.8*100
         
    # =============================================================================
    #         fig1, axs1 = plt.subplots(math.ceil(nbchannels/2),2,figsize=(6,fig_height))            
    # =============================================================================
            fig1, axs1 = plt.subplots(math.ceil(nbchannels/2),2)   
            fig1.suptitle('Data Streamed', fontsize=16)
            fig1.canvas.mpl_connect('button_press_event', on_click)
            mngr = plt.get_current_fig_manager()
            mngr.window.setGeometry(990,100,640,fig_height)
        
            # If odd number of subplots, delete the last one
            # Also, find the bottom left subplot
            if nbchannels % 2 != 0:        
                a,b = divmod(nbchannels,2)
                fig1.delaxes(axs1[a][b])
                subplotToShow = nbchannels - 1
            else:            
                subplotToShow = nbchannels - 2  
                
            for subplt in range(0,nbchannels):        
                # create a variable for the line so we can later update it
                a,b = divmod(subplt,2)
                line1.append(axs1[a][b].plot(x_vec,channelsData[subplt],'-',alpha=0.8,color='green'))
                axs1[a][b].set_ylim([-3, 3])
                axs1[a][b].set_title('Channel ' + str(subplt), y = 0.9)
                axs1[a][b].set_facecolor('black')
                axs1[a][b].grid(False)  
                
                # Makes axis visible only for the bottom left subplot
                if subplt != subplotToShow:
                    axs1[a][b].set_yticklabels([])
                    axs1[a][b].set_xticklabels([])
                else:
                    axs1[a][b].set_ylabel('Amplitude (uV)')
                    axs1[a][b].set_xticklabels([])
                
            plt.show()
            print('Raw Data Figure created')
            
        if do_fft:   
            
            # Create thread to calculate fft and iterate data matrix
            thread_calculate_fft = threading.Thread(target = calculate_fft, daemon = True)
            thread_calculate_fft.start()        
            
            if line2==[]:
                # this is the call to matplotlib that allows dynamic plotting
                plt.ion()
                    
# =============================================================================
#                 fig2, axs2 = plt.subplots(math.ceil(nbchannels/2),2,figsize=(6, fig_height))
# =============================================================================
                fig2, axs2 = plt.subplots(math.ceil(nbchannels/2),2)
                fig2.suptitle('Spectrum Power', fontsize=16)
                fig2.canvas.mpl_connect('button_press_event', on_click) 
                mngr = plt.get_current_fig_manager()
                mngr.window.setGeometry(340,100,640,fig_height)         
                    
                for subplt in range(0,nbchannels):        
                    # create a variable for the line so we can later update it
                    a,b = divmod(subplt,2)
                    line2.append(axs2[a][b].plot(f_axis,fftData[subplt],'-',alpha=1, color = 'yellow'))
                    
                    # Adjust subplot appearance
                    axs2[a][b].set_ylim([0, 0.6])
                    axs2[a][b].set_xlim([0, 200])
                    axs2[a][b].set_title('Channel ' + str(subplt), y = 0.9)
                    axs2[a][b].set_facecolor('black')
                    axs2[a][b].grid(False)  
                    
                    # Makes axis visible only for the bottom left subplot
                    if subplt != subplotToShow:
                        axs2[a][b].set_yticklabels([])
                        axs2[a][b].set_xticklabels([])
                    else:
                        axs2[a][b].set_ylabel('Norm. Spec. Power')
                        axs2[a][b].set_xlabel('Frequency (Hz)')
                    
                plt.show()
                print('FFT Figure created')
            
        plt.pause(2)
        
    # =============================================================================
    #     thread_plot = threading.Thread(target = live_plotter, daemon = True)
    #     thread_plot.start()
    #     
    #     thread_plot_fft = threading.Thread(target = live_plotter_fft, daemon = True)
    #     thread_plot_fft.start()
    # =============================================================================
        
        while run == True:        
            live_plotter()
                
        print('Exiting...')
    
if __name__ == '__main__':
    main()