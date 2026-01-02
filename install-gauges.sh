#!/bin/bash
# =============================================================================
# Standalone install script for reTerminal system gauges dashboard
# Creates gauges.py + sets up auto-start at boot via systemd
# Run as:   bash this_script.sh    (preferably as user pi with sudo)
# =============================================================================

set -e

echo "============================================================="
echo "  reTerminal Gauges Dashboard - Full Standalone Installer"
echo "  (CPU Temp + Freq + Usage, RAM, Disk, Network, Uptime)"
echo "============================================================="
echo ""

# 1. Update & install dependencies
echo "→ Updating system and installing required packages..."
sudo apt update -y
sudo apt install -y \
    python3-pip \
    python3-pyqt5 \
    python3-matplotlib \
    python3-psutil \
    python3-numpy

# Optional: upgrade pip just in case
python3 -m pip install --upgrade pip --user

echo "→ Dependencies installed."

# 2. Create the gauges.py file
echo "→ Writing improved gauges.py script..."
cat > ~/gauges.py << 'EOF'
import sys
import os
import time
import psutil
import numpy as np
from datetime import timedelta
from matplotlib import cm
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Wedge, Circle
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QScreen

def degree_range(n):
    start = np.linspace(0, 180, n + 1, endpoint=True)[:-1]
    end = np.linspace(0, 180, n + 1, endpoint=True)[1:]
    mid_points = start + ((end - start) / 2.)
    return np.c_[start, end], mid_points

def rot_text(ang):
    return np.degrees(np.radians(ang) * np.pi / np.pi - np.radians(90))

class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        self.fig = fig

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.cpu_canvas     = MatplotlibCanvas(self, width=4.2, height=4.2, dpi=100)
        self.cpu_small_canvas = MatplotlibCanvas(self, width=2.2, height=2.2, dpi=100)
        self.ram_canvas     = MatplotlibCanvas(self, width=4,   height=2.2, dpi=100)
        self.ram_line_canvas= MatplotlibCanvas(self, width=4,   height=1.8, dpi=100)
        self.disk_canvas    = MatplotlibCanvas(self, width=4,   height=4,   dpi=100)

        self.status_label = QLabel("Network: -- | Uptime: --")
        self.status_label.setStyleSheet("color: cyan; font-size: 14px; background: transparent;")

        main_layout = QHBoxLayout()

        left_col = QVBoxLayout()
        left_col.addWidget(self.cpu_canvas)
        left_col.addWidget(self.cpu_small_canvas)
        left_widget = QWidget(); left_widget.setLayout(left_col)

        ram_col = QVBoxLayout()
        ram_col.addWidget(self.ram_canvas)
        ram_col.addWidget(self.ram_line_canvas)
        ram_widget = QWidget(); ram_widget.setLayout(ram_col)

        right_col = QVBoxLayout()
        right_col.addWidget(self.disk_canvas)
        right_col.addStretch()
        right_col.addWidget(self.status_label, alignment=Qt.AlignBottom | Qt.AlignRight)
 # self.status_label.setAlignment(Qt.AlignRight)  # aligns the text itself to the right
        right_widget = QWidget(); right_widget.setLayout(right_col)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(ram_widget)
        main_layout.addWidget(right_widget)

        self.setLayout(main_layout)

        self.cpu_history = []
        self.ram_history = []
        self.last_net_io = psutil.net_io_counters()
        self.last_net_time = time.time()
        self.boot_time = psutil.boot_time()  # actual system boot time

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(1500)

        # Try to detect and fullscreen on built-in display
        screens = QApplication.screens()
        for screen in screens:
            if 'DSI' in screen.name() or screen.geometry().width() == 1280:
                self.setGeometry(screen.geometry())
                self.showFullScreen()
                break

    def update_plots(self):
        # CPU Temp
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                cpu_temp = float(f.read().strip()) / 1000
        except:
            cpu_temp = 0.0

        # CPU Freq
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq') as f:
                cpu_freq = float(f.read().strip()) / 1000
        except:
            cpu_freq = 0.0

        cpu_percent = psutil.cpu_percent(interval=None)
        ram_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent

        # Network
        now = time.time()
        io = psutil.net_io_counters()
        dt = now - self.last_net_time
        down = up = 0.0
        if dt > 0.1:
            down = (io.bytes_recv - self.last_net_io.bytes_recv) / dt / 1024 / 1024
            up   = (io.bytes_sent - self.last_net_io.bytes_sent) / dt / 1024 / 1024
        self.last_net_io = io
        self.last_net_time = now

        # Uptime
        uptime_sec = time.time() - self.boot_time
        uptime_str = str(timedelta(seconds=int(uptime_sec))).split(',')[0].strip()

        self.status_label.setText(f"↓ {down:.1f} ↑ {up:.1f} MB/s   |   Uptime: {uptime_str}")

        self.cpu_history.append(cpu_freq)
        if len(self.cpu_history) > 60: self.cpu_history.pop(0)

        self.ram_history.append(ram_percent)
        if len(self.ram_history) > 60: self.ram_history.pop(0)

        self.update_gauge(self.cpu_canvas.ax, cpu_temp, 0, 100, 'CPU Temp', '°C',
                          with_line=True, history=self.cpu_history, min_line=600, max_line=2000,
                          warning_temp=cpu_temp)
        self.cpu_canvas.draw()

        self.update_gauge(self.cpu_small_canvas.ax, cpu_percent, 0, 100, 'CPU %', '%',
                          radius=0.38, needle_length=0.22, smaller=True)
        self.cpu_small_canvas.draw()

        self.cpu_canvas.ax.text(0, 0.15, f"{cpu_freq:.0f} MHz", ha='center', va='center',
                                fontsize=22, fontweight='bold', color='white')
        self.cpu_canvas.draw()

        self.update_gauge(self.ram_canvas.ax, ram_percent, 0, 100, 'RAM', '%')
        self.ram_canvas.draw()

        self.update_line(self.ram_line_canvas.ax, self.ram_history, 'RAM % (60s)', 0, 100)
        self.ram_line_canvas.draw()

        self.update_gauge(self.disk_canvas.ax, disk_percent, 0, 100, 'Disk', '%')
        self.disk_canvas.draw()

    def update_line(self, ax, data, title, ymin, ymax):
        ax.clear()
        ax.plot(data, color='#00ccff', linewidth=2)
        ax.set_title(title, fontsize=11, color='white')
        ax.set_ylim(ymin, ymax)
        ax.set_xlim(0, len(data)-1)
        ax.grid(True, alpha=0.2, color='gray')
        ax.tick_params(colors='gray', labelsize=8)
        ax.set_facecolor('black')

    def update_gauge(self, ax, value, min_val, max_val, title, unit,
                     with_line=False, history=None, min_line=0, max_line=1,
                     radius=0.4, needle_length=0.3, smaller=False, warning_temp=None):
        ax.clear()

        if warning_temp is not None:
            if warning_temp > 75: ax.set_facecolor('#440000')
            elif warning_temp > 60: ax.set_facecolor('#442200')
            else: ax.set_facecolor('black')

        if with_line and history:
            x = np.linspace(-0.35, 0.35, len(history))
            scaled = np.clip((np.array(history) - min_line) / (max_line - min_line), 0, 1)
            y = -0.22 + 0.16 * scaled
            ax.plot(x, y, color='#0066cc', alpha=0.7, lw=2.5)

        n_segments = 20
        colors = 'RdYlGn_r' if smaller else 'RdYlGn'
        cmap = cm.get_cmap(colors, n_segments)
        gauge_colors = cmap(np.arange(n_segments))

        ang_range, _ = degree_range(n_segments)

        for ang, c in zip(ang_range, gauge_colors):
            ax.add_patch(Wedge((0,0), radius, *ang, facecolor='w', lw=2))
            ax.add_patch(Wedge((0,0), radius, *ang, width=0.10, facecolor=c, lw=2, alpha=0.6))

        n_labels = 5 if smaller else 6
        labels = [str(int(max_val - i*(max_val-min_val)/(n_labels-1))) for i in range(n_labels)]
        label_angs = np.linspace(0, 180, n_labels)
        label_size = 10 if smaller else 12

        for ang, lab in zip(label_angs, labels):
            ax.text(0.35*np.cos(np.radians(ang)), 0.35*np.sin(np.radians(ang)), lab,
                    ha='center', va='center', fontsize=label_size, fontweight='bold', color='white',
                    rotation=rot_text(ang))

        value_size = 24 if smaller else 28
        ax.text(0, -0.08, f"{value:.1f}{unit}", ha='center', va='center',
                fontsize=value_size, fontweight='bold', color='white')

        ax.text(0, -0.32, title, ha='center', va='center',
                fontsize=14 if smaller else 18, fontweight='bold', color='lightgray')

        scale = (value - min_val) / (max_val - min_val) if max_val > min_val else 0
        pos = 180 - 180 * scale
        ax.arrow(0, 0, needle_length*np.cos(np.radians(pos)), needle_length*np.sin(np.radians(pos)),
                 width=0.035, head_width=0.085, head_length=0.09, fc='white', ec='black')
        ax.add_patch(Circle((0,0), 0.025, facecolor='black'))
        ax.add_patch(Circle((0,0), 0.012, facecolor='white', zorder=11))

        ax.set_frame_on(False)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis('equal')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setStyleSheet("background-color: black;")
    window.show()
    sys.exit(app.exec_())
EOF

chmod +x ~/gauges.py

# 3. Create systemd service
echo "→ Creating systemd service file..."
sudo bash -c "cat > /etc/systemd/system/gauges-dashboard.service" << 'EOF'
[Unit]
Description=ReTerminal System Gauges Dashboard
After=graphical.target

[Service]
User=pi
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/gauges.py
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
EOF

# 4. Activate service
echo "→ Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable gauges-dashboard.service
sudo systemctl restart gauges-dashboard.service

echo ""
echo "============================================================="
echo "               Installation completed!"
echo ""
echo "The gauges dashboard should now be visible on the built-in display."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status gauges-dashboard.service     → check status"
echo "  sudo systemctl stop gauges-dashboard.service        → stop"
echo "  sudo systemctl start gauges-dashboard.service       → start"
echo "  journalctl -u gauges-dashboard.service -n 50 -f     → live logs"
echo ""
echo "Enjoy your beautiful system monitor! 🚀"
echo "============================================================="