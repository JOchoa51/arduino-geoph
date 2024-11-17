import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt
import serial
import numpy as np
import datetime
import time
import sys
from scipy.fft import rfft, rfftfreq
from scipy.signal import firwin, savgol_filter
import struct
from filterpy.kalman import KalmanFilter
import re


class ADS1115:

	def __init__(self, port, filter, mode, file_type, save_frequency=10) -> None:
		"""Initialize the ADS1115 class with serial communication and plotting settings."""
		self.gain_dict = {
			'GAIN_TWOTHIRDS': [0.1875, 6144],
			'GAIN_ONE': [0.125, 4096],
			'GAIN_TWO': [0.0625, 2048],
			'GAIN_FOUR': [0.03125, 1024],
			'GAIN_EIGHT': [0.015625, 512],
			'GAIN_SIXTEEN': [0.0078125, 256]
			}

		self.write_timer = time.perf_counter()
		self.read_ino(r"C:\Users\huevo\Documents\GeofisicaFIUNAM\Proyectos personales\Sismometro DIY\ADS1115_OLEDdraw\ADS1115_OLEDdraw.ino")

		# Validate mode
		if mode not in ['plot', 'file', 'both', 'print']:
			raise ValueError("Mode must be 'plot', 'file', 'both' or 'print'")
		if self.gain_str not in self.gain_dict.keys():
			raise ValueError("Gain must be 'GAIN_TWOTHIRDS', 'GAIN_ONE', 'GAIN_TWO', 'GAIN_FOUR', 'GAIN_EIGHT' or 'GAIN_SIXTEEN'")
		
		self.port = port
		# self.baud = baud
		# self.sampling_rate = sampling_rate
		self.gain_factor = self.gain_dict[self.gain_str][0]
		self.mode = mode
		self.reconnect_attempts = 5  # Number of reconnect attempts

		# Initialize serial communication
		self.ser = self.connect_serial()
		
		print(f'\033[1;34mSample rate: \033[0m{self.sampling_rate} Hz')
		print(f'\033[1;34mInitial gain factor: \033[0m{self.gain_str} ({self.gain_factor} mV/bit)\n')
		# Create the main window for the plots
		if mode in ['plot', 'both']:
			self.app = QApplication([])
			self.win = pg.GraphicsLayoutWidget(show=True)
			self.create_plot(which='both')
			self.win.setMinimumSize(1200, 700)  # or setFixedSize(800, 600)
			self.win.closeEvent = self.on_close
		else:
			self.app = None
			self.win = None
		
		self.buffer_size = 500
		self.data = np.zeros(self.buffer_size)  # Buffer for raw data
		self.filtered_data = np.zeros(self.buffer_size)  # Buffer for filtered data
		self.data_index = 0  # Track current index in the circular buffer
		self.file_buffer = []
		self.save_frequency = save_frequency # Buffer size for file writes

		self.update_counter = 0
		self.update_size = 50   # Plot update interval
		self.file_type = file_type
		self.filename = self.get_current_filename()
		self.file = open(self.filename, 'a') if mode in ['file', 'both'] else None
		self.filter_coeffs = None  # Store filter coefficients
		
		self.filter = filter
		if self.filter:
			self.init_kalman()

	def read_ino(self, file):
		with open(file, 'r') as ino:
			lines = ino.readlines()
			fs = lines[15]
			baud = lines[68]
			fs_match = re.search(r'[\d.]+', fs)
			baud_match = re.search(r'\((.*?)\)', baud)
			if fs_match:
				self.sampling_rate = float(fs_match.group())
			if baud_match:
				self.baud = int(baud_match.group(1))

			gain = lines[47]
			gain_match = re.search(r'int g = (\d+);', gain)

			if gain_match:
				gain_num = int(gain_match.group(1))
				self.gain_str = list(self.gain_dict)[gain_num]
				

	def update_gain(self, ser_line):
		# Split the serial line into individual entries
		# line = self.ser.readline().decode('utf-8', errors='ignore').strip()
		gain_match = re.match(r'^(GAIN_[A-Z]+)$', ser_line)
		if gain_match:
			self.gain_str = gain_match.group(1) # Add the gain setting to the list
		self.gain_factor = self.gain_dict[self.gain_str][0]
		print(f'\n\033[1;31mNew gain factor: \033[0m{self.gain_str} ({self.gain_factor} mV/bit)\n')
		

	def init_kalman(self):
		# Initialize the KalmanFilter object for 1D data (voltage)
		self.kf = KalmanFilter(dim_x=1, dim_z=1)
		
		# Set up the state transition and measurement matrices
		self.kf.F = np.array([[1]])  # No change in voltage between steps
		self.kf.H = np.array([[1]])  # Direct measurement of voltage

		# Initialize the state covariance (P), process noise (Q), and measurement noise (R)
		self.kf.P *= 100.  # Initial uncertainty in state covariance
		self.kf.R = 5       # Measurement noise variance
		self.kf.Q = np.array([[1]])  # Process noise covariance

		# Initial state estimate (voltage = 0)
		self.kf.x = np.array([[0]])

	def on_close(self, event):
		sys.exit(0)

	def connect_serial(self):
		"""Attempt to connect to the serial port."""
		print(f"\nConnecting to serial port {self.port} at {self.baud} baud rate...")
		for attempt in range(self.reconnect_attempts):
			time.sleep(0.5)
			try:
				ser = serial.Serial(self.port, self.baud)
				print(f"\033[0;32mConnected to serial port on attempt {attempt + 1} \n\033[0m")
				print('\aStarting...\n')
				time.sleep(0.5)
				return ser
			except serial.SerialException:
				print(f"\nFailed to connect to serial port on attempt {attempt + 1}")
				time.sleep(0.5)
		
		print(f"\n\033[0;31mCould not connect to serial port after {self.reconnect_attempts} attempts at {datetime.datetime.now()}\033[0m")
		# self.close_file()
		quit()
		return None

	def update_plot_lims(self):
		self.time_plot.setYRange(-self.gain_dict[self.gain_str][1], self.gain_dict[self.gain_str][1])  # Set voltage plot range

	def create_plot(self, which='time') -> None:
		"""Creates the plot object, containing time, frequency, or both domains."""
		if which == 'time':
			# Time-Domain Plot
			self.time_plot = self.win.addPlot(title="Real-Time Signal")
			self.time_plot.setYRange(-self.gain_dict[self.gain_str][1], self.gain_dict[self.gain_str][1])  # Set voltage plot range
			self.time_plot.showGrid(x=True, y=True)
			self.time_plot.setLabel('left', 'Voltage (mV)')
			self.time_plot.setLabel('bottom', 'Time (s)')
			self.time_curve = self.time_plot.plot()
		if which == 'fft':
			# FFT Plot
			self.fft_plot = self.win.addPlot(title="FFT of Signal")
			self.fft_plot.showGrid(x=True, y=True)
			self.fft_plot.setXRange(0.5, self.sampling_rate / 2)  # Set voltage plot range from 0 to Nyquist frequency
			self.fft_plot.setLabel('left', 'Magnitude')
			self.fft_plot.setLabel('bottom', 'Frequency (Hz)')
			self.fft_curve = self.fft_plot.plot()
			self.time_plot = self.win.addPlot(title="Real-Time Signal")
			self.time_plot.setYRange(-self.gain_dict[self.gain_str][1], self.gain_dict[self.gain_str][1])  # Set voltage plot range
		if which == 'both':
			self.time_plot = self.win.addPlot(title="Real-Time Signal")
			self.time_plot.showGrid(x=True, y=True)
			self.time_plot.setYRange(-self.gain_dict[self.gain_str][1], self.gain_dict[self.gain_str][1])  # Set voltage plot range
			self.time_plot.setLabel('left', 'Voltage (mV)')
			self.time_plot.setLabel('bottom', 'Time (s)')
			self.time_curve = self.time_plot.plot()
			# FFT Plot
			self.fft_plot = self.win.addPlot(title="FFT of Signal")
			self.fft_plot.showGrid(x=True, y=True)
			self.fft_plot.setXRange(0.5, self.sampling_rate / 2)  # Set voltage plot range from 0 to Nyquist frequency
			self.fft_plot.setLabel('left', 'Magnitude')
			self.fft_plot.setLabel('bottom', 'Frequency (Hz)')
			self.fft_curve = self.fft_plot.plot()

	def set_firfilter(self, fc, numtaps):
		"""Create and store FIR filter coefficients."""
		self.filter_coeffs = firwin(numtaps, fc / (self.sampling_rate / 2))  # FIR filter coefficients (normalized frequency)

	def get_current_filename(self):
		"""Return a filename based on the current date."""
		if self.file_type == 'text':
			return datetime.datetime.now().strftime("%d-%m-%Y") + ".txt"
		if self.file_type == 'binary':
			return datetime.datetime.now().strftime("%d-%m-%Y") + ".bin"

	def update_file(self):
		"""Manage file updates on day change."""
		new_filename = self.get_current_filename()
		if new_filename != self.filename:
			self.file.close()
			self.filename = new_filename
			self.file = open(self.filename, 'a')

	def update_ticks(self):
		"""Update x-axis ticks with time labels."""
		tick_positions = np.linspace(0, len(self.data) - 1, num=6)
		tick_labels = []
		for pos in tick_positions:
			time_point = datetime.datetime .now() - datetime.timedelta(seconds=(len(self.data) - pos) / self.sampling_rate)
			timestamp_str = time_point.strftime("%H:%M:%S.") + str(time_point.microsecond // 1000).zfill(3)
			tick_labels.append((pos, timestamp_str))
		self.time_plot.getAxis('bottom').setTicks([tick_labels])

	def update(self, fft=True):
		"""Update the plot and/or file based on the mode."""

		try:
			# Read and parse serial data
			line = self.ser.readline().decode('utf-8', errors='ignore').strip()
			y = None
			try:
				y = float(line) * self.gain_factor
				self.data[self.data_index] = y
				self.data_index = (self.data_index + 1) % self.buffer_size
			except ValueError:
				self.update_gain(line)
				if self.mode in ['plot','both']:
					self.update_plot_lims()

			# Get current timestamp only once per update
			now = datetime.datetime.now()

			# Update the circular buffer

			# ! Apply filtering once
			if self.filter:
				# if self.filter_coeffs is None:
				# 	raise ValueError("Filter coefficients not set")
				# self.filtered_data = self.kalman_filter(self.data)
				self.filtered_data = self.savgol(self.data, window_size=20)

			# Update the plot every `update_size` iterations
			self.update_counter += 1
			if self.update_counter >= self.update_size and self.mode in ['plot', 'both']:
				if self.filter:
					self.time_curve.setData(np.roll(self.filtered_data, -self.data_index))  # Update filtered data
				else:
					self.time_curve.setData(np.roll(self.data, -self.data_index))  # Update raw data

				self.update_ticks()  # Update x-axis ticks

				# FFT calculation and update
				if fft and (self.update_counter % self.update_size == 0):  # Update FFT less frequently
					if self.filter:
						yf = np.abs(rfft(self.filtered_data))  # Compute FFT on filtered data
					else:
						yf = np.abs(rfft(self.data))  # Compute FFT on raw data
					xf = rfftfreq(self.buffer_size, 1 / self.sampling_rate)  # Frequency axis
					if self.fft_curve is not None:
						self.fft_curve.setData(xf, np.abs(yf))  # Update FFT plot

				self.update_counter = 0

			# Prepare data for file writing (filter only once)
			if self.mode in ['file', 'both'] and y is not None:
				data_to_write = self.filtered_data[self.data_index] if self.filter else y

				if self.file_type == 'binary':
					packed_data = struct.pack('dd', now.timestamp(), data_to_write)
					self.file_buffer.append(packed_data)
				else:
					self.file_buffer.append(f"{now.timestamp()},{data_to_write:.7f}\n")

			# Write to file in batches
			# ! if len(self.file_buffer) >= self.save_frequency and self.mode in ['file', 'both']:
			current_time = time.perf_counter()

			if (current_time - self.write_timer) >= self.save_frequency and self.mode in ['file', 'both']:
				self.update_file()  # Check if a new day has started
				with open(self.filename, 'ab' if self.file_type == 'binary' else 'a') as f:
					if self.file_type == 'binary':
						f.write(b''.join(self.file_buffer))  # Write all packed data in one go
					else:
						f.write(''.join(self.file_buffer))  # Write the buffer to the file
				print(f'\a\033[1;34mBuffer written\033[0m at {datetime.datetime.now()}')
				self.file_buffer.clear()

				self.write_timer = current_time

		except serial.SerialException:
			print("Serial connection lost. Attempting to reconnect...")
			self.ser = self.connect_serial()
			if self.ser is None:
				self.close_file()
				print(f"File closed due to connection loss at {datetime.datetime.now()}")
		except (ValueError, UnicodeDecodeError) as e:
			print(f"Error: {e}")

	def kalman_filter(self, data):
			# Pre-allocate an array for filtered data
		filtered_data = np.empty(len(data))
		
		# Time the process
		start_time = time.perf_counter()

		# Apply the Kalman filter to each data point in `data`
		for i, measurement in enumerate(data):
			self.kf.predict()  # Predict next state (voltage)
			self.kf.update([measurement])  # Update with the new measurement

			# Store filtered voltage in pre-allocated array
			filtered_data[i] = self.kf.x[0][0]

		end_time = time.perf_counter()
		# print(f"Processing time: {end_time - start_time:.6f} seconds")
		
		# Return the filtered data
		return filtered_data
	
	def savgol(self, data, window_size=20, order=2):
		"""Apply Savitzky-Golay filter to data."""
		return savgol_filter(x=data, 
							window_length=window_size, 
							polyorder=order,
							mode='interp')
	
	def close_file(self):
		"""Close the file if it's open."""
		if self.file:
			self.file.close()
			self.file = None

	def run(self) -> None:
		"""Start the application."""
		if self.mode == 'print':
			self.print_only()

		elif self.mode == 'file':
			while True:
				try:
					self.update(fft=False)
					time.sleep(1 / self.sampling_rate)  # Control the sampling rate
				except serial.SerialException:
					print("\nSerial connection lost. Attempting to reconnect...")
					self.ser = self.connect_serial()
					if self.ser is None:
						self.close_file()
						print(f"\nFile closed due to connection loss at {datetime.datetime.now()}")
						break
				except (ValueError, UnicodeDecodeError) as e:
					print(f"Error: {e}")

		elif self.mode == 'plot':
			if self.filter:
				self.set_firfilter(30, 50)  # Set filter coefficients
			timer = QTimer()
			timer.timeout.connect(lambda: self.update(fft=True))
			timer.start(int(1000 / self.sampling_rate))
			self.app.exec_()  # Start the Qt event loop to keep the application running

		elif self.mode == 'both':
			self.set_firfilter(10, 50)  # Set filter coefficients
			timer = QTimer()
			timer.timeout.connect(lambda: self.update(fft=True))
			timer.start(int(1000 / self.sampling_rate))
			self.app.exec_()  # Start the Qt event loop to keep the application running

			while True:
				try:
					self.update(fft=True, filter=True)
					self.app.processEvents()  # Allow Qt to process events
				except serial.SerialException:
					print("Serial connection lost. Attempting to reconnect...")
					self.ser = self.connect_serial()
					if self.ser is None:
						self.close_file()
						print(f"File closed due to connection loss at {datetime.datetime.now()}")
						break
				except (ValueError, UnicodeDecodeError) as e:
					print(f"Error: {e}")

		# Ensure file is closed when the app finishes
		if self.file:
			self.file.close()

	def print_only(self):
		buffer_size = 500  # Size of the circular buffer
		data_buffer = np.zeros(buffer_size)  # Initialize a buffer with zeros
		buffer_index = 0  # Index to keep track of where to insert new data
		total_entries = 0  # Counter to track the number of data points added
		beep_cooldown = 0.22
		last_beep = 0.0
		while True:
			try:
				# Read and parse serial data
				line = self.ser.readline().decode('utf-8', errors='ignore').strip()
				y = float(line) * self.gain_factor
				now = datetime.datetime.now()

				# Update the buffer with the new value
				data_buffer[buffer_index] = y
				buffer_index = (buffer_index + 1) % buffer_size
				total_entries += 1

				# Calculate the mean of the last 500 (or fewer) values
				if total_entries < buffer_size:
					mean_value = np.mean(data_buffer[:total_entries])
				else:
					mean_value = np.mean(data_buffer)

				# Check if value is within ±0.1 of zero
				if abs(y) <= 1:
					# Print in green for values within ±0.1 of zero
					print(f"\033[1;32m{now}: {y}\033[0m")
					# if time.time() -last_beep >= beep_cooldown:
					# 	print("\a")
					# 	last_beep = time.time()
				elif abs(y - mean_value) >= 5:
					# Print in blue for significant deviation
					print(f"\033[1;31m{now}: {y}\033[0m")
				else:
					# Print normally
					print(f"{now}: {y}")

			except serial.SerialException:
				print("Serial connection lost. Attempting to reconnect...")
				self.ser = self.connect_serial()
				if self.ser is None:
					print(f"File closed due to connection loss at {datetime.datetime.now()}")
					break
			except (ValueError, UnicodeDecodeError) as e:
				print(f"Error: {e}")

if __name__ == '__main__':
	start = time.perf_counter()
	try:
		app = ADS1115(port='COM5', filter=False, mode='file', file_type='binary', save_frequency=15)
		app.run()
	except KeyboardInterrupt:
		end = time.perf_counter()
		print('\n\033[1;31mProgram ended!\033[0m')
		print(f"\033[1;96mTotal execution time: \033[0m{end - start:.2f} seconds")  # Print the 
		print(f"\033[1;96mScript ended at \033[0m{datetime.datetime.now()}\n")