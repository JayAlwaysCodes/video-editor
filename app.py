import os
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFileDialog, QLineEdit, QSpinBox, QGroupBox,
                             QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx.all import crop, resize

class VideoProcessor(QThread):
    progress_updated = pyqtSignal(int)
    processing_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, input_video1, input_video2, output_path, parent=None):
        super().__init__(parent)
        self.input_video1 = input_video1
        self.input_video2 = input_video2
        self.output_path = output_path
        self.running = True

    def run(self):
        try:
            # Load clips
            clip1 = VideoFileClip(self.input_video1).subclip(0, 5)  # First 5 sec of video1
            clip2 = VideoFileClip(self.input_video2)  # Full video2
            
            processed_clips = [clip1]  # Start with the 5-sec intro
            total_frames = int(clip2.fps * clip2.duration)
            processed_frames = 0
            
            current_time = 0
            total_duration = clip2.duration
            
            while current_time < total_duration and self.running:
                # Play 15 sec normally
                end_15sec = min(current_time + 15, total_duration)
                normal_clip = clip2.subclip(current_time, end_15sec)
                processed_clips.append(normal_clip)
                current_time = end_15sec
                processed_frames += int(15 * clip2.fps)
                self.progress_updated.emit(int(100 * processed_frames / total_frames))
                
                if current_time >= total_duration:
                    break
                
                # Zoom 40% or 20% alternately
                zoom_level = 40 if (len(processed_clips) // 2) % 2 == 0 else 20
                zoom_clip = self.zoom_on_random_spot(clip2.subclip(current_time), zoom_level, 5)
                processed_clips.append(zoom_clip)
                current_time += 5
                processed_frames += int(5 * clip2.fps)
                self.progress_updated.emit(int(100 * processed_frames / total_frames))
                
                if current_time >= total_duration:
                    break
                
                # Skip 3 sec
                current_time += 3
                processed_frames += int(3 * clip2.fps)
                self.progress_updated.emit(int(100 * processed_frames / total_frames))
            
            if self.running:
                # Combine all clips and save
                final_clip = concatenate_videoclips(processed_clips)
                final_clip.write_videofile(self.output_path, codec="libx264", fps=24)
                self.processing_finished.emit(self.output_path)
                
        except Exception as e:
            self.error_occurred.emit(str(e))

    def zoom_on_random_spot(self, clip, zoom_level, duration):
        """Zooms on a random portion of the video."""
        w, h = clip.size
        zoom_factor = zoom_level / 100.0
        zoom_w, zoom_h = int(w * zoom_factor), int(h * zoom_factor)
        
        # Pick a random spot to zoom
        x = random.randint(0, w - zoom_w)
        y = random.randint(0, h - zoom_h)
        
        # Create zoomed clip
        zoomed_clip = crop(clip, x1=x, y1=y, x2=x+zoom_w, y2=y+zoom_h).set_duration(duration)
        zoomed_clip = resize(zoomed_clip, (w, h))  # Scale back to original dimensions
        
        return zoomed_clip

    def stop(self):
        self.running = False

class VideoEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Video Editor")
        self.setGeometry(100, 100, 600, 400)
        
        self.processor = None
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # Input Video 1
        group1 = QGroupBox("Intro Video (First 5 seconds)")
        layout1 = QHBoxLayout()
        self.input1_path = QLineEdit()
        self.input1_path.setPlaceholderText("Select first video file...")
        btn_browse1 = QPushButton("Browse")
        btn_browse1.clicked.connect(lambda: self.browse_file(self.input1_path))
        layout1.addWidget(self.input1_path)
        layout1.addWidget(btn_browse1)
        group1.setLayout(layout1)
        layout.addWidget(group1)
        
        # Input Video 2
        group2 = QGroupBox("Main Video")
        layout2 = QHBoxLayout()
        self.input2_path = QLineEdit()
        self.input2_path.setPlaceholderText("Select main video file...")
        btn_browse2 = QPushButton("Browse")
        btn_browse2.clicked.connect(lambda: self.browse_file(self.input2_path))
        layout2.addWidget(self.input2_path)
        layout2.addWidget(btn_browse2)
        group2.setLayout(layout2)
        layout.addWidget(group2)
        
        # Output Settings
        group3 = QGroupBox("Output Settings")
        layout3 = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output file...")
        btn_browse_output = QPushButton("Browse")
        btn_browse_output.clicked.connect(self.browse_output_file)
        layout3.addWidget(self.output_path)
        layout3.addWidget(btn_browse_output)
        group3.setLayout(layout3)
        layout.addWidget(group3)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_bar)
        
        # Edit Button
        self.btn_edit = QPushButton("Process Video")
        self.btn_edit.clicked.connect(self.process_video)
        layout.addWidget(self.btn_edit)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file_path:
            line_edit.setText(file_path)
            
    def browse_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", "", "MP4 Files (*.mp4)")
        if file_path:
            if not file_path.lower().endswith('.mp4'):
                file_path += '.mp4'
            self.output_path.setText(file_path)
            
    def process_video(self):
        input1 = self.input1_path.text()
        input2 = self.input2_path.text()
        output = self.output_path.text()
        
        if not all([input1, input2, output]):
            QMessageBox.warning(self, "Error", "Please select all input and output files!")
            return
            
        if not os.path.exists(input1):
            QMessageBox.warning(self, "Error", f"File not found: {input1}")
            return
            
        if not os.path.exists(input2):
            QMessageBox.warning(self, "Error", f"File not found: {input2}")
            return
            
        self.btn_edit.setEnabled(False)
        self.progress_bar.setValue(0)
        
        self.processor = VideoProcessor(input1, input2, output)
        self.processor.progress_updated.connect(self.update_progress)
        self.processor.processing_finished.connect(self.processing_complete)
        self.processor.error_occurred.connect(self.show_error)
        self.processor.start()
        
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        
    def processing_complete(self, output_path):
        self.btn_edit.setEnabled(True)
        QMessageBox.information(self, "Success", f"Video processing complete!\nSaved to: {output_path}")
        
    def show_error(self, message):
        self.btn_edit.setEnabled(True)
        QMessageBox.critical(self, "Error", message)
        
    def closeEvent(self, event):
        if self.processor and self.processor.isRunning():
            self.processor.stop()
            self.processor.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    editor = VideoEditorApp()
    editor.show()
    app.exec_()