import sys
import time
import psutil
import numpy as np
import matplotlib.pyplot as plt
import mplcyberpunk
from datetime import timedelta
from matplotlib import cm
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Wedge, Circle
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QScreen

# Apply cyberpunk style globally
plt.style.use("cyberpunk")

def degree_range(n):
    start = np.linspace(0, 180, n + 1, endpoint=True)[:-1]
    end = np.linspace(0, 180, n + 1, endpoint=True)[1:]
    return np.c_[start, end], np.mean([start, end], axis=0)

def rot_text(ang):
    return np.degrees(np.radians(ang) - np.radians(90))

class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, facecolor='black')
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        self.fig = fig

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Canvases
        self.cpu_canvas = MatplotlibCanvas(self, width=4.5, height=4.5, dpi=100)
        self.cpu_small_canvas = MatplotlibCanvas(self, width=2.5, height=2.5, dpi=100)
        self.ram_canvas = MatplotlibCanvas(self, width=4, height=2.2, dpi=100)
        self.ram_line_canvas = MatplotlibCanvas(self, width=4, height=1.8, dpi=100)
        self.disk_canvas = MatplotlibCanvas(self, width=4, height=4, dpi=100)

        # Header and status
        self.header_label = QLabel("SYSTEM MONITOR")
        self.header_label.setAlignment(Qt.AlignCenter)
        self.header_label.setStyleSheet("""
            color: #ff00ff;
            font-size: 36px;
            font-weight: bold;
            font-family: monospace;
            background: transparent;
            margin: 10px;
        """)

        self.status_label = QLabel("Network: -- | Uptime: --")
        self.status_label.setStyleSheet("""
            color: #00ffff;
            font-size: 18px;
            font-weight: bold;
            background: transparent;
            padding: 10px;
        """)
        self.status_label.setAlignment(Qt.AlignRight)

        # Layout
        outer_layout = QVBoxLayout()
        outer_layout.addWidget(self.header_label)

        main_layout = QHBoxLayout()

        left_col = QVBoxLayout()
        left_col.addWidget(self.cpu_canvas)
        left_col.addWidget(self.cpu_small_canvas)
        left_widget = QWidget()
        left_widget.setLayout(left_col)

        ram_col = QVBoxLayout()
        ram_col.addWidget(self.ram_canvas)
        ram_col.addWidget(self.ram_line_canvas)
        ram_widget = QWidget()
        ram_widget.setLayout(ram_col)

        right_col = QVBoxLayout()
        right_col.addWidget(self.disk_canvas)
        right_col.addStretch()
        right_col.addWidget(self.status_label, alignment=Qt.AlignRight | Qt.AlignBottom)
        right_widget = QWidget()
        right_widget.setLayout(right_col)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(ram_widget)
        main_layout.addWidget(right_widget)

        outer_layout.addLayout(main_layout)
        self.setLayout(outer_layout)

        # Data
        self.cpu_history = []
        self.ram_history = []
        self.last_net_io = psutil.net_io_counters()
        self.last_net_time = time.time()

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(1500)

        # Fullscreen on built-in display
        screens = QApplication.screens()
        for screen in screens:
            if 'DSI' in screen.name() or screen.geometry().width() <= 1280:
                self.setGeometry(screen.geometry())
                self.showFullScreen()
                break

        self.setStyleSheet("background-color: black;")

    def update_plots(self):
        # System stats
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                cpu_temp = float(f.read().strip()) / 1000
        except:
            cpu_temp = 0.0

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
        dt = now - self.last_net_time if self.last_net_time else 1
        down = (io.bytes_recv - self.last_net_io.bytes_recv) / dt / 1024 / 1024
        up = (io.bytes_sent - self.last_net_io.bytes_sent) / dt / 1024 / 1024
        self.last_net_io = io
        self.last_net_time = now

        # Uptime (real system uptime)
        uptime_str = str(timedelta(seconds=int(time.time() - psutil.boot_time()))).split('.')[0]

        self.status_label.setText(f"↓ {down:.1f} ↑ {up:.1f} MB/s   |   Uptime: {uptime_str}")

        # History
        self.cpu_history.append(cpu_freq)
        if len(self.cpu_history) > 60: self.cpu_history.pop(0)
        self.ram_history.append(ram_percent)
        if len(self.ram_history) > 60: self.ram_history.pop(0)

        # Update gauges and lines
        self.update_gauge(self.cpu_canvas.ax, cpu_temp, 0, 100, 'CPU TEMP', '°C',
                          with_line=True, history=self.cpu_history, min_line=600, max_line=2000,
                          warning_temp=cpu_temp)
        self.cpu_canvas.draw()

        self.update_gauge(self.cpu_small_canvas.ax, cpu_percent, 0, 100, 'CPU %', '%',
                          radius=0.38, needle_length=0.22, smaller=True)
        self.cpu_small_canvas.draw()

        # CPU freq overlay
        self.cpu_canvas.ax.text(0, 0.15, f"{cpu_freq:.0f} MHz",
                                ha='center', va='center', fontsize=24,
                                fontweight='bold', color='#00ffff')
        self.cpu_canvas.draw()

        self.update_gauge(self.ram_canvas.ax, ram_percent, 0, 100, 'RAM', '%')
        self.ram_canvas.draw()

        self.update_line(self.ram_line_canvas.ax, self.ram_history, 'RAM % (60s)', 0, 100)
        self.ram_line_canvas.draw()

        self.update_gauge(self.disk_canvas.ax, disk_percent, 0, 100, 'DISK', '%')
        self.disk_canvas.draw()

    def update_line(self, ax, data, title, ymin, ymax):
        ax.clear()
        ax.plot(data, color='#00ffff', linewidth=4)
        mplcyberpunk.add_glow_effects()  # Neon glow!
        ax.set_title(title, fontsize=12, color='#ff00ff')
        ax.set_ylim(ymin, ymax)
        ax.set_xlim(0, len(data)-1)
        ax.grid(True, alpha=0.1, color='#00ffff')
        ax.tick_params(colors='#00ffff', labelsize=8)
        ax.set_facecolor('black')

    def update_gauge(self, ax, value, min_val, max_val, title, unit,
                     with_line=False, history=None, min_line=0, max_line=1,
                     radius=0.4, needle_length=0.3, smaller=False, warning_temp=None):
        ax.clear()
        ax.set_facecolor('black')

        # Warning background (cyberpunk dark red/purple)
        needle_color = '#ff00ff'
        if warning_temp is not None:
            if warning_temp > 75:
                ax.set_facecolor('#220011')
                needle_color = '#ff0055'
            elif warning_temp > 60:
                ax.set_facecolor('#221100')
                needle_color = '#ff6600'

        # History line with glow (CPU freq)
        if with_line and history:
            x = np.linspace(-0.35, 0.35, len(history))
            scaled = np.clip((np.array(history) - min_line) / (max_line - min_line), 0, 1)
            y = -0.22 + 0.16 * scaled
            ax.plot(x, y, color='#00ffff', linewidth=4)
            mplcyberpunk.add_glow_effects()

        # Gauge segments - vibrant plasma colormap
        n_segments = 20
        cmap = cm.get_cmap('plasma', n_segments)
        gauge_colors = cmap(np.arange(n_segments))

        ang_range, _ = degree_range(n_segments)

        for ang, c in zip(ang_range, gauge_colors):
            ax.add_patch(Wedge((0,0), radius, *ang, facecolor='black', lw=2))
            ax.add_patch(Wedge((0,0), radius, *ang, width=0.10, facecolor=c, lw=2, alpha=0.7))

        # Labels
        n_labels = 5 if smaller else 6
        labels = [str(int(max_val - i*(max_val-min_val)/(n_labels-1))) for i in range(n_labels)]
        label_angs = np.linspace(0, 180, n_labels)
        label_size = 10 if smaller else 12

        for ang, lab in zip(label_angs, labels):
            ax.text(0.35*np.cos(np.radians(ang)), 0.35*np.sin(np.radians(ang)), lab,
                    ha='center', va='center', fontsize=label_size, fontweight='bold',
                    color='#00ffff', rotation=rot_text(ang))

        # Value and title
        ax.text(0, -0.08, f"{value:.1f}{unit}", ha='center', va='center',
                fontsize=28 if not smaller else 24, fontweight='bold', color='#00ffff')

        ax.text(0, -0.32, title, ha='center', va='center',
                fontsize=18 if not smaller else 14, fontweight='bold', color='#ff00ff')

        # Needle with manual glow
        scale = (value - min_val) / (max_val - min_val) if max_val > min_val else 0
        pos = 180 - 180 * scale
        nx = needle_length * np.cos(np.radians(pos))
        ny = needle_length * np.sin(np.radians(pos))

        # Glow under needle
        ax.plot([0, nx*1.1], [0, ny*1.1], color='#ffffff', lw=10, alpha=0.2)
        ax.plot([0, nx], [0, ny], color=needle_color, lw=5, alpha=0.7)

        # Main needle
        ax.arrow(0, 0, nx, ny, width=0.03, head_width=0.08, head_length=0.1,
                 fc=needle_color, ec='#00ffff', lw=2)

        ax.add_patch(Circle((0,0), 0.03, facecolor='black', zorder=10))
        ax.add_patch(Circle((0,0), 0.015, facecolor='#00ffff', zorder=11))

        ax.set_frame_on(False)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis('equal')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())