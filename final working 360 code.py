import os
import sys
import cv2
import numpy as np
import glob
import pyzed.sl as sl
from PIL import Image
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget
from PyQt5.QtCore import Qt
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

# Ensure directory exists
def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# Capture images from ZED 2i
def capture_images_zed():
    images_dir = "images"
    ensure_directory_exists(images_dir)

    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.HD1080  # Adjust as needed
    init_params.camera_fps = 30
    zed = sl.Camera()

    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print("❌ Error: Could not open ZED 2i camera.")
        return False

    runtime_parameters = sl.RuntimeParameters()
    image = sl.Mat()
    photo_count = 0

    print("Press 'c' to capture a photo, or 'q' to quit.")

    while True:
        if zed.grab(runtime_parameters) == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image, sl.VIEW.LEFT)
            frame = image.get_data()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)  # Convert BGRA to BGR

            cv2.imshow("ZED 2i Camera", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                photo_count += 1
                photo_path = os.path.join(images_dir, f"photo_{photo_count}.jpg")
                cv2.imwrite(photo_path, frame)
                print(f"📸 Photo saved: {photo_path}")
            elif key == ord('q'):
                break

    zed.close()
    cv2.destroyAllWindows()
    return True

# Panorama stitching
def create_panorama():
    image_paths = sorted(glob.glob("images/*.jpg"))
    images = [cv2.imread(img) for img in image_paths]

    if any(img is None for img in images):
        print("❌ Error: Some images failed to load.")
        return None

    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    (status, panorama) = stitcher.stitch(images)

    if status == cv2.Stitcher_OK:
        panorama_path = "panorama.jpg"
        cv2.imwrite(panorama_path, panorama)
        print(f"✅ Panorama created successfully! Saved to {panorama_path}")
        return panorama_path
    else:
        print("❌ Failed to create panorama. Try improving image alignment.")
        return None

# OpenGL viewer
class PanoramaViewer(QOpenGLWidget):
    def __init__(self, image_path, parent=None):  # ✅ Fixed __init__
        super().__init__(parent)  # ✅ Fixed super().__init__
        self.image_path = image_path
        self.texture_id = None
        self.last_x, self.last_y = 0, 0
        self.yaw, self.pitch, self.roll = 0, 0, 0
        self.mouse_button_pressed = None

    def initializeGL(self):
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0, 0, 0, 1)
        self.texture_id = self.loadTexture(self.image_path)

    def resizeGL(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        
        # MATCH ZED 2i's FoV & Aspect Ratio
        aspect_ratio = width / height
        gluPerspective(110, aspect_ratio, 0.1, 100)  # 110° horizontal FoV

        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(self.pitch, 1, 0, 0)  # Up/Down correct
        glRotatef(self.yaw, 0, 0, 1)   # Left/Right correct
        self.drawSphere()

    def drawSphere(self):
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        quadric = gluNewQuadric()
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricOrientation(quadric, GLU_INSIDE)
        gluSphere(quadric, 5, 50, 50)

    def loadTexture(self, image_path):
        img = Image.open(image_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        img_data = np.array(img, dtype=np.uint8)

        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)

        return texture_id

    def mousePressEvent(self, event):
        self.last_x, self.last_y = event.x(), event.y()
        self.mouse_button_pressed = event.button()

    def mouseMoveEvent(self, event):
        dx = event.x() - self.last_x
        dy = event.y() - self.last_y
        self.last_x, self.last_y = event.x(), event.y()

        if self.mouse_button_pressed == Qt.LeftButton:
            self.yaw -= dx * 0.2  # Left moves left, right moves right
            self.pitch -= dy * 0.2  # Up moves up, down moves down
        elif self.mouse_button_pressed == Qt.RightButton:
            self.roll -= dx * 0.2  # Keeping roll unchanged
        self.update()

    def mouseReleaseEvent(self, event):
        self.mouse_button_pressed = None

# Main application
class MainWindow(QMainWindow):
    def __init__(self, image_path):  # ✅ Fixed __init__
        super().__init__()  # ✅ Fixed super().__init__
        self.setWindowTitle("360° Panorama Viewer")
        self.viewer = PanoramaViewer(image_path)
        self.setCentralWidget(self.viewer)
        self.resize(1920, 1080)  # Default to ZED 2i resolution

# Run the application
if __name__ == "__main__":
    if capture_images_zed():
        panorama_path = create_panorama()
        if panorama_path:
            app = QApplication(sys.argv)
            window = MainWindow(panorama_path)  # ✅ Now it works correctly!
            window.show()
            sys.exit(app.exec_())
