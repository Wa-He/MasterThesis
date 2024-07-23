Control Software Code:

GUI_TVAC_PID (main script):
	opens a GUI from which the system can be controlled

THS_Control:
	class for control of the transient hot strip

TVAC_Control:
	class for control of TVAC heating/cooling systems

class_PID:
	class with PID functionality

ArduinoRelay_Control:
	class to control a arduino to switch relays for the heating/cooling system of the TVAC
	ArduinoRelay/ holds programming of the arduino as ArduinoRelay.ino

USBRelay_Control:
	class to alternatively control relays with a USB relay instead of an arduino

SDM_Control:
	class to control the siglent digital multimeter and configuration of measurement

ListInputApp:
	list input widget for the GUI

SliderApp:
	slider widget for the GUI plots

Pressure_readMaxiGauge:
	script to read pressure data from a Pfeiffer MaxiGauge and save to file

Pressure_readCamera:
	seperate script to save camera images of the pressure reading (if no pc interface is present)


Data/:
	Default directory where collected data will be saved
	Archive/: all files ever created
	Conductivity Measurements/: sorted accumulation of conducted measurements
	






