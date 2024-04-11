#!/usr/bin/env python
"""Subsystem E unit testing script."""
#Use IDLE to run the testing automation
#Avoid Sublime Text

import pyvisa
import time
from numpy import *
from matplotlib.pyplot import *
import matplotlib.pyplot as plt

import sys

__author__ = 'Sean Victor Hum'
__copyright__ = 'Copyright 2023'
__license__ = 'GPL'
__version__ = '1.0'
__email__ = 'sean.hum@utoronto.ca'

def wait_for_powerhorse_test():
    print("Press Enter to start Maximum Powerhorse test and '!' to terminate.")

    while True:
        user_input = input("Press Enter to continue: ")

        if user_input == '':
            print("Start Maximum Powerhorse test...")
            break
        if (user_input == '!'):
            print('Testing terminated.')
            scope.write(':WGEN:OUTP OFF')
            scope.close()
            supply.close()
            sys.exit(1)
        else:
            print("Invalid input. Press Enter to continue.")

# Open instrument connection(s)
rm = pyvisa.ResourceManager()
school_ip = True
#school_ip = False
if (school_ip):
    scope = rm.open_resource('TCPIP0::192.168.0.253::hislip0::INSTR')
    supply = rm.open_resource('TCPIP0::192.168.0.251::5025::SOCKET')
else:
    scope = rm.open_resource('TCPIP0::192.168.2.253::hislip0::INSTR')
    supply = rm.open_resource('TCPIP0::192.168.2.251::5025::SOCKET')

# Define string terminations and timeouts
scope.write_termination = '\n'
scope.read_termination = '\n'
supply.write_termination = '\n'
supply.read_termination = '\n'
scope.timeout = 10000           # 10s
supply.timeout = 10000          # 10s

# Set probe scaling to 1:1
scope.write('CHANnel1:PROBe +1.0')
scope.write('CHANnel2:PROBe +1.0')

# Setup trigger
scope.write(':TRIG:SWEep AUTO')
scope.write(':TRIG:EDGE:SOURce CHAN1')
scope.write(':TRIG:EDGE:LEVel +0.0')

# Disable power supply output and wavegen output
supply.write('OUTP OFF, (@2)')
scope.write(':WGEN:OUTP OFF')


# Turn on power supply and set up wavegen
supply.write('VOLT 12, (@2)')
supply.write('CURR 0.3, (@2)')
supply.write('OUTP ON, (@2)')
scope.write(':WGEN:FUNC SIN')
scope.write(':WGEN:FREQ 1.400E+07')


# Set wavegen amplitude and enable
drive_amplitude = 1.0          # Set to input drive amplitude required
scope.write(':WGEN:volt %e' % (drive_amplitude))
scope.write(':WGEN:OUTP ON')

# Setup acquisition
scope.write(':TIMebase:SCAL +5.0E-08') # 50 ns/div
scope.write(':CHAN1:COUP AC')
scope.write(':CHAN1:DISP ON')
scope.write(':FFT:DISP OFF')

# Query power supply and scope for single point measurement
V = float(supply.query('VOLT? (@2)'))
Iidle = float(supply.query('MEAS:CURR? CH2'))
Iactive = float(supply.query('MEAS:CURR? CH2'))
Pactive = V*Iactive
Vrms = float(scope.query(':MEAS:VRMS? CHAN1'))
Pout = (Vrms*Vrms)/50
print('Voltage Output:', Vrms, 'Vrms')
print('Power on Antenna: ', Pout, 'W')

#reset for Fourier Transform Analysis
supply.write('VOLT 12, (@2)')
supply.write('CURR 0.3, (@2)')
supply.write('CURR PROT:STAT ON, (@2)')
supply.write('OUTP ON, (@2)')

A_dBV = zeros(5, float)         # Vector to store first 5 harmonic amplitudes

# Setup FFT
scope.write(':CHAN1:DISP OFF')
scope.write(':FFT:DISP ON')
scope.write(':FFT:CENT 37.5 MHz')
scope.write(':FFT:SPAN 75 MHz')
scope.write(':FFT:SOUR CHAN1')
scope.write(':TIMebase:SCAL +1.0E-06') # 1 us/div
scope.write(':MARKer:X1Y1source FFT')
scope.write(':MARKer:X2Y2source FFT')
scope.write(':MARK:MODE WAV')

f0 = float(scope.query('WGEN:FREQ?'))

# Measure harmonics
scope.write(':MARKer:X1P %e' % (f0))
scope.write(':MARKer:X2P %e' % (2*f0))
time.sleep(1)
A_dBV[0] = float(scope.query(':MARK:Y1P?'))
A_dBV[1] = float(scope.query(':MARK:Y2P?'))

scope.write(':MARKer:X1P %e' % (3*f0))
scope.write(':MARKer:X2P %e' % (4*f0))
time.sleep(1)
A_dBV[2] = float(scope.query(':MARK:Y1P?'))
A_dBV[3] = float(scope.query(':MARK:Y2P?'))

scope.write(':MARKer:X1P %e' % (5*f0))
time.sleep(1)
A_dBV[4] = float(scope.query(':MARK:Y1P?'))

# Calculate power spectrum
n = arange(1, 6)
Pcoeffs = (10**(A_dBV/20))**2/50
P_dBW = 10*log10(Pcoeffs)


P1 = Pcoeffs[0]

eff = P1/Pactive


#write into database
with open('Extra Test Results.txt', 'w') as file:
    file.write(f'Power Data: \n')
    file.write(f'Supply voltage: {V} V\n')
    file.write(f'Current draw (idle): {Iidle} A\n')
    file.write(f'Current draw (active): {Iactive} A\n')
    file.write(f'DC power consumption: {Pactive} W\n')
    file.write(f'Frequency Data:  \n')
    file.write(f'Measured harmonics (dBV): {A_dBV} \n')
    file.write(f'RF power output at 14 MHz: {P1} W\n')
    file.write(f'DC-to-RF power conversion efficiency: {eff*100} %\n')

# Calculate THD
A = 10**(A_dBV/20)
A2 = A**2
numerator = sqrt(sum(A2[1:]))
denominator = A[0]
THD = numerator/denominator
print('THD:', THD*100, '%')


# Restore display
scope.write(':CHAN1:DISP ON')
scope.write(':FFT:DISP OFF')
scope.write(':TIMebase:SCAL +5.0E-08') # 5 us/div

# Frequency sweep
N = 41                          # Number of frequency points 
freq = arange(N)/(N-1)*14e6 + 4e6 # Array of frequency points
Vout = zeros(N, float)

print('Measuring frequency response...')
for k in range(N):
    scope.write(':WGEN:FREQ %e' % freq[k])
    time.sleep(1)
    Vout[k] = float(scope.query(':MEAS:VRMS? CHAN1'))
    #print(freq[k], Vout[k])
    
savetxt('frequency vs Vout.txt', (freq, Vout))
    

# Save and plot data
Prf = Vout**2/50
savetxt('pout.txt', (freq, Prf))
savetxt('spectrum.txt', (n, Pcoeffs))

# Plot Pout vs frequency (dBW)
fig, ax = subplots()
ax.plot(freq/1e6, 10*log10(Prf))
ax.set_xlabel('Frequency [MHz]')
ax.set_ylabel('RF output power [dBW]')
ax.grid(True)
ax.set_title('PA Frequency Response for Vin = %.1f Vpp' % (drive_amplitude))
savefig('pout_dBW.png')

# Plot Pout vs frequency (W)
fig, ax = subplots()
ax.plot(freq/1e6, Prf)
plot(freq/1e6, 20*log10(ampl_q/50e-3))
ax.set_xlabel('Frequency [MHz]')
ax.set_ylabel('RF output power [W]')
ax.set_yscale('log')
ax.set_ylim((1e-3, 10))
ax.grid(True)
ax.set_title('PA Frequency Response for Vin = %.1f Vpp' % (drive_amplitude))
savefig('pout.png')

# Plot output spectrum
fig, ax = subplots()
ax.stem(n, Pcoeffs, use_line_collection=True)
ax.set_ylabel('RF output power [W]')
ax.set_yscale('log')
ax.grid(True)
ax.set_title('PA Output Spectrum: f = %.1f MHz, eff=%.1f %%, THD=%.1f %%' % (f0/1e6, eff*100, THD*100))
savefig('spectrum.png')

#Bode Plot
start_freq = 1e6   # 1 MHz
stop_freq = 100e6   # 100 MHz
num_points = 100    

freqs = np.linspace(start_freq, stop_freq, num_points)

Vrms_values = []   
ID = 0.3           

for freq in freqs: 
    scope.write(f':WGEN:FREQ {freq:.6e}')
    time.sleep(1)      
    Vrms = float(scope.query(':MEAS:VRMS? CHAN1'))  
    Vrms_values.append(Vrms)


Vrms_mag_dB = 20 * np.log10(np.abs(Vrms_values) / ID)

Vrms_phase_deg = np.angle(Vrms_values, deg=True)

fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 10))

ax_mag.plot(freqs / 1e6, Vrms_mag_dB, label='Magnitude (dB)', color='b')
ax_mag.set_xlabel('Frequency (MHz)')
ax_mag.set_ylabel('Magnitude (dB)')
ax_mag.set_title('Bode Plot: Magnitude vs. Frequency')
ax_mag.grid(True)
ax_mag.legend()

ax_phase.plot(freqs / 1e6, Vrms_phase_deg, label='Phase (degrees)', color='r')
ax_phase.set_xlabel('Frequency (MHz)')
ax_phase.set_ylabel('Phase (degrees)')
ax_phase.set_title('Bode Plot: Phase vs. Frequency')
ax_phase.grid(True)
ax_phase.legend()

plt.tight_layout()
plt.savefig('bode_plot.png')
print('Bode Plot Finished!')


#DC condition sweep
supply.write('VOLT 12, (@2)')
supply.write('CURR PROT:STAT OFF, (@2)')

min_current = 0.01  # Minimum current 
max_current = 1  # Maximum current 
num_points = 20    

supply_currents = np.linspace(min_current, max_current, num_points)

ID = []  
V = []   

wait_for_powerhorse_test()

for current in supply_currents:

    supply.write(f'CURR {current}, (@2)')

    Vrms = float(scope.query(':MEAS:VRMS? CHAN1'))
    
    supply.write('OUTP OFF, (@2)')

    time.sleep(0.01)

    ID.append(current)
    V.append(Vrms)

Vmax = np.max(V)
print("Maximum Output Voltage (Vmax):", Vmax)

supply.write('OUTP OFF, (@2)')

plt.figure()
plt.plot(ID, V, marker='o', linestyle='-', color='b')
plt.xlabel('DC Current[A]')
plt.ylabel('Output Vrms[V]')
plt.grid(True)
plt.title('DC Current vs. Output Vrms')
plt.savefig('current_vs_vrms.png')
print('Max Output Sweep Done!')

print('All Tests Completed!')

scope.write(':WGEN:OUTP OFF')
scope.close()
supply.write('OUTP OFF, (@2)')
supply.close()
