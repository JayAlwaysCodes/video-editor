import os
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QFileDialog, QLineEdit, QGroupBox,
                             QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
from moviepy.video.fx.all import crop
from PIL import Image
import sys
import numpy as np

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
            with VideoFileClip(self.input_video1) as clip1, VideoFileClip(self.input_video2) as clip2:
                # Use first 16 seconds of video1 as intro
                intro_clip = clip1.subclip(0, min(16, clip1.duration))
                processed_clips = [intro_clip]
                
                total_frames = int(clip2.fps * clip2.duration)
                processed_frames = 0
                current_time = 0
                total_duration = clip2.duration
                
                while current_time < total_duration and self.running:
                    # Add 15-second normal segment
                    end_15sec = min(current_time + 45, total_duration)
                    normal_clip = clip2.subclip(current_time, end_15sec)
                    processed_clips.append(normal_clip)
                    processed_frames += int((end_15sec - current_time) * clip2.fps)
                    self.progress_updated.emit(min(100, int(100 * processed_frames / total_frames)))
                    current_time = end_15sec  # Advance time after normal segment
                    
                    if current_time >= total_duration:
                        break
                    
                    # Add 5-second zoomed segment with fixed 30% zoom
                    end_zoom = min(current_time + 5, total_duration)
                    zoom_clip = self.zoom_on_random_spot(clip2.subclip(current_time, end_zoom), 50, end_zoom - current_time)
                    processed_clips.append(zoom_clip)
                    processed_frames += int(5 * clip2.fps)
                    self.progress_updated.emit(min(100, int(100 * processed_frames / total_frames)))
                    current_time = end_zoom  # Advance time after zoomed segment
                    
                    if current_time >= total_duration:
                        break
                    
                    # Skip 3 seconds
                    current_time += 10
                    processed_frames += int(10 * clip2.fps)
                    self.progress_updated.emit(min(100, int(100 * processed_frames / total_frames)))
                
                if self.running:
                    # Concatenate clips
                    final_clip = concatenate_videoclips(processed_clips, method="compose")
                    
                    # Add watermark spanning the bottom
                    watermark = (TextClip("VIDHUB_AFRO", fontsize=40, color='white', font='Arial')
                                .set_opacity(0.5)
                                .set_duration(final_clip.duration)
                                .set_position(('center', 'bottom'), relative=True))
                    final_clip = CompositeVideoClip([final_clip, watermark], size=final_clip.size)
                    
                    # Write output
                    final_clip.write_videofile(self.output_path, codec="libx264", fps=24, audio_codec="aac")
                    self.processing_finished.emit(self.output_path)
        
        except FileNotFoundError:
            self.error_occurred.emit("One of the input video files could not be found.")
        except Exception as e:
            self.error_occurred.emit(f"Processing failed: {str(e)}")

    def zoom_on_random_spot(self, clip, zoom_level, duration):
        """Zooms on a random portion of the video."""
        w, h = clip.size
        zoom_factor = 1 + (zoom_level / 100.0)  # Convert percentage to scale factor
        zoom_w, zoom_h = int(w / zoom_factor), int(h / zoom_factor)
        
        # Ensure zoomed area fits within video bounds
        x1 = random.randint(0, max(0, w - zoom_w))
        y1 = random.randint(0, max(0, h - zoom_h))
        x2 = x1 + zoom_w
        y2 = y1 + zoom_h
        
        # Crop the clip
        cropped_clip = crop(clip, x1=x1, y1=y1, x2=x2, y2=y2).set_duration(duration)
        
        # Custom resize using Pillow with LANCZOS
        def custom_resize(frame, t=None):
            img = Image.fromarray(frame)
            resized_img = img.resize((w, h), resample=Image.LANCZOS)
            return np.array(resized_img)
        
        # Apply custom resize to each frame
        zoomed_clip = cropped_clip.fl(lambda gf, t: custom_resize(gf(t), t))
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

        group1 = QGroupBox("Intro Video (First 16 seconds)")
        layout1 = QHBoxLayout()
        self.input1_path = QLineEdit()
        self.input1_path.setPlaceholderText("Select intro video file...")
        self.input1_path.setReadOnly(True)
        btn_browse1 = QPushButton("Browse")
        btn_browse1.clicked.connect(lambda: self.browse_file(self.input1_path))
        layout1.addWidget(self.input1_path)
        layout1.addWidget(btn_browse1)
        group1.setLayout(layout1)
        layout.addWidget(group1)

        group2 = QGroupBox("Main Video")
        layout2 = QHBoxLayout()
        self.input2_path = QLineEdit()
        self.input2_path.setPlaceholderText("Select main video file...")
        self.input2_path.setReadOnly(True)
        btn_browse2 = QPushButton("Browse")
        btn_browse2.clicked.connect(lambda: self.browse_file(self.input2_path))
        layout2.addWidget(self.input2_path)
        layout2.addWidget(btn_browse2)
        group2.setLayout(layout2)
        layout.addWidget(group2)

        group3 = QGroupBox("Output Settings")
        layout3 = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output file...")
        self.output_path.setReadOnly(True)
        btn_browse_output = QPushButton("Browse")
        btn_browse_output.clicked.connect(self.browse_output_file)
        layout3.addWidget(self.output_path)
        layout3.addWidget(btn_browse_output)
        group3.setLayout(layout3)
        layout.addWidget(group3)

        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        self.btn_edit = QPushButton("Process Video")
        self.btn_edit.clicked.connect(self.process_video)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_processing)
        self.btn_cancel.setEnabled(False)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def browse_file(self, line_edit):
        default_dir = "/mnt/c/Users/YourUser/Videos"  # Replace 'YourUser' with your Windows username
        if not os.path.exists(default_dir):
            default_dir = "/mnt/c"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", default_dir, "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file_path:
            line_edit.setText(file_path)

    def browse_output_file(self):
        default_dir = "/mnt/c/Users/YourUser/Videos"  # Replace 'YourUser' with your Windows username
        if not os.path.exists(default_dir):
            default_dir = "/mnt/c"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", default_dir, "MP4 Files (*.mp4)")
        if file_path:
            if not file_path.lower().endswith('.mp4'):
                file_path += '.mp4'
            self.output_path.setText(file_path)

    def process_video(self):
        input1 = self.input1_path.text()
        input2 = self.input2_path.text()
        output = self.output_path.text()

        if not all([input1, input2, output]):
            QMessageBox.warning(self, "Error", "Please select all input and output files.")
            return

        if not os.path.isfile(input1):
            QMessageBox.warning(self, "Error", f"Intro video not found: {input1}")
            return

        if not os.path.isfile(input2):
            QMessageBox.warning(self, "Error", f"Main video not found: {input2}")
            return

        output_dir = os.path.dirname(output) or '.'
        if not os.access(output_dir, os.W_OK):
            QMessageBox.warning(self, "Error", "Cannot write to output directory.")
            return

        self.btn_edit.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)

        self.processor = VideoProcessor(input1, input2, output)
        self.processor.progress_updated.connect(self.update_progress)
        self.processor.processing_finished.connect(self.processing_complete)
        self.processor.error_occurred.connect(self.show_error)
        self.processor.start()

    def cancel_processing(self):
        if self.processor and self.processor.isRunning():
            self.processor.stop()
            self.btn_edit.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            QMessageBox.information(self, "Cancelled", "Video processing cancelled.")

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def processing_complete(self, output_path):
        self.btn_edit.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "Success", f"Video processing complete!\nSaved to: {output_path}")

    def show_error(self, message):
        self.btn_edit.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(0)
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        if self.processor and self.processor.isRunning():
            self.processor.stop()
            self.processor.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = VideoEditorApp()
    editor.show()
    sys.exit(app.exec_())