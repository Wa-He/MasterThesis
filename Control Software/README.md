# Control Software

The control software was implemented using Python's tkinter module. The entire software can be controlled from the GUI, which is to be executed as main.


#### GUI_TVAC_PID (main script):
opens a GUI from which the system can be controlled

#### THS_Control:
class for control of the transient hot strip

#### TVAC_Control:
class for control of TVAC heating/cooling systems

#### class_PID:
class with PID functionality

#### ArduinoRelay_Control:
class to control an arduino to switch relays for the heating/cooling system of the TVAC<br>
ArduinoRelay/ holds programming of the arduino in the form of ArduinoRelay.ino

#### USBRelay_Control:
class to alternatively control relays with a USB relay instead of an arduino

#### SDM_Control:
class to control the siglent digital multimeter and configuration of measurement

#### ListInputApp:
list input widget for the GUI

#### SliderApp:
slider widget for the GUI plots

#### Pressure_readMaxiGauge:
script to read pressure data from a Pfeiffer MaxiGauge and save to file

#### Pressure_readCamera:
seperate script to save camera images of the pressure reading (if no pc interface is present)


#### Data/:
Default directory where collected data will be saved to <br>
Archive/: holds all measurement data acquised during the cource of the thesis<br>
Conductivity Measurements/: contains a sorted accumulation of the conducted measurement data and evaluation plots
	






